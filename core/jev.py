"""JevPredictor: asks TypeSafe's Jev model (System One) how the supplier will respond.

API confirmed against the installed typesafe-sdk 0.7.5:
    AsyncTypeSafeClient(api_key=..., model=..., timeout=...)
    await client.system_one(state=..., questions={name: Choice(instructions, criteria)}, retry=..., timeout=...)
    response.choices[name].probabilities -> {"accept": p, "counter": p, "walk": p}
Default model is "jev-latest" (override with TYPESAFE_MODEL).

How it plugs into the search: Jev only sees the negotiation history, not the
sampled floor, so it is asked once per turn about the real candidate moves
(depth 0). Its answer is blended with the heuristic for each sampled supplier.
Playouts deeper than one move use the heuristic alone, so a turn costs one
round of API calls. Candidates are batched several per call (one Choice
question each) and the batches run concurrently. Any error or timeout falls
back to the heuristic and is logged.
"""
import asyncio
import json
import logging
import os

from typesafe_sdk import AsyncTypeSafeClient, Choice, RetryPolicy, TypeSafeAuthenticationError

from core.offers import Offer
from core.predictor import HeuristicPredictor, PredictState, SupplierPredictor

log = logging.getLogger("dealroom.jev")

MODEL = os.environ.get("TYPESAFE_MODEL", "jev-latest")
CALL_TIMEOUT_S = 1.2      # leaves room inside search's 2 s budget
BATCH_SIZE = 4            # candidate offers per system_one call
JEV_WEIGHT = 0.5          # blend with the heuristic's floor-aware estimate
LABELS = ("accept", "counter", "walk")

CRITERIA = {
    "accept": "The supplier accepts this exact price and payment timing.",
    "counter": "The supplier rejects it but sends a counteroffer and keeps negotiating.",
    "walk": "The supplier ends the negotiation with no deal.",
}


def _state_text(state: PredictState) -> str:
    """What Jev reads: the negotiation so far, without anything the buyer can't see."""
    ctx = state.context
    lines = [{"from": h["from"], "kind": h["kind"], "price": h.get("price"),
              "pay_in_days": h.get("pay_in_days"), "message": h.get("message", "")}
             for h in ctx.get("history", [])]
    return json.dumps({
        "situation": "A small business's buyer is negotiating a repeat bulk order with a supplier.",
        "item": ctx.get("item"), "quantity": ctx.get("quantity"),
        "supplier_list_price": state.list_price, "supplier_current_ask": state.ask,
        "round": state.round, "history": lines,
    })


def _question(offer: Offer) -> Choice:
    pay = "paid immediately (prepay)" if offer.pay_in_days == 0 else f"paid in {offer.pay_in_days} days"
    return Choice(
        instructions=f"The buyer now offers ${offer.price:.2f} per unit, {pay}. "
                     f"How does the supplier respond?",
        criteria=CRITERIA,
    )


class JevPredictor(SupplierPredictor):
    def __init__(self):
        self.heuristic = HeuristicPredictor()
        self._cache: dict = {}          # (round, ask, candidates) -> list of jev probs
        self.last_source = "jev"
        self.disabled = False           # set after an auth error: no point retrying every turn

    # ---- SupplierPredictor -------------------------------------------------
    def predict(self, state: PredictState, candidates: list[Offer]) -> list[dict]:
        base = self.heuristic.predict(state, candidates)
        if state.depth > 0:
            return base
        jev = self._jev_probs(state, candidates)
        if jev is None:
            return base
        return [self._blend(h, j) for h, j in zip(base, jev)]

    # ---- internals ---------------------------------------------------------
    def _jev_probs(self, state: PredictState, candidates: list[Offer]) -> list[dict] | None:
        if self.disabled:
            self.last_source = "heuristic (jev disabled)"
            return None
        key = (state.round, state.ask, tuple(candidates))
        if key not in self._cache:
            try:
                self._cache[key] = asyncio.run(self._ask_all(state, candidates))
                self.last_source = "jev"
            except TypeSafeAuthenticationError:
                log.warning("TYPESAFE_API_KEY was rejected; using the heuristic for the rest of this run")
                self.disabled = True
                self._cache[key] = None
                self.last_source = "heuristic (jev disabled)"
            except Exception as e:   # timeout, network, bad response: fall back this turn
                log.warning("Jev call failed (%s: %s); using heuristic", type(e).__name__, e)
                self._cache[key] = None
                self.last_source = "heuristic (jev failed)"
        return self._cache[key]

    async def _ask_all(self, state: PredictState, candidates: list[Offer]) -> list[dict]:
        """Batch candidates into a few system_one calls and run them concurrently."""
        text = _state_text(state)
        batches = [candidates[i:i + BATCH_SIZE] for i in range(0, len(candidates), BATCH_SIZE)]
        # A fresh client per turn: each asyncio.run() has its own event loop. Reads TYPESAFE_API_KEY.
        async with AsyncTypeSafeClient(model=MODEL, timeout=CALL_TIMEOUT_S) as client:
            results = await asyncio.wait_for(
                asyncio.gather(*(self._ask_batch(client, text, b) for b in batches)),
                timeout=CALL_TIMEOUT_S + 0.3,
            )
        return [p for batch in results for p in batch]

    async def _ask_batch(self, client: AsyncTypeSafeClient, text: str, batch: list[Offer]) -> list[dict]:
        questions = {f"offer_{i}": _question(o) for i, o in enumerate(batch)}
        resp = await client.system_one(
            state=text, questions=questions,
            retry=RetryPolicy(max_retries=0), timeout=CALL_TIMEOUT_S,
        )
        out = []
        for name in questions:
            probs = resp.choices[name].probabilities
            total = sum(probs.get(label, 0.0) for label in LABELS) or 1.0
            out.append({label: probs.get(label, 0.0) / total for label in LABELS})
        return out

    @staticmethod
    def _blend(h: dict, j: dict) -> dict:
        return {k: (1 - JEV_WEIGHT) * h[k] + JEV_WEIGHT * j[k] for k in LABELS}
