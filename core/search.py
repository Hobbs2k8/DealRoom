"""Look-ahead search: pick the buyer's next offer.

Each turn: build ~8 candidate moves (4 price levels x pay now / pay in 45 days).
For each candidate, sample plausible suppliers (floors) from the belief, play out
up to DEPTH rounds with the predictor, and average the dollar value. Hard 2 s
time limit; if time runs out we return the best candidate scored so far.
"""
import random
import time
from dataclasses import dataclass

from core.belief import CONCESSION_RATES, FloorBelief, terms_factor
from core.offers import PAY_LATER, PAY_NOW, Offer
from core.predictor import PredictState, SupplierPredictor
from core.score import deal_value

TIME_LIMIT_S = 2.0
SAMPLES = 40
DEPTH = 3

# Owner modes: how hard to push on price, and how much a walk-away hurts.
MODES = {
    "passive":    {"price_shift": 1.02, "walk_cost_frac": 0.10},
    "balanced":   {"price_shift": 1.00, "walk_cost_frac": 0.05},
    "aggressive": {"price_shift": 0.97, "walk_cost_frac": 0.02},
}


@dataclass
class SearchInput:
    belief: FloorBelief
    ask: float                 # supplier's current ask
    last_offer: float | None   # buyer's previous offer price (never go below it)
    list_price: float
    quantity: int
    round: int
    max_rounds: int            # buyer's guess of supplier patience
    cash: dict                 # see score.deal_value
    mode: str = "balanced"
    context: dict | None = None  # negotiation history for predictors that read it (Jev)


def candidate_moves(inp: SearchInput) -> list[Offer]:
    """4 price levels x 2 payment timings, never below our last offer or above the ask."""
    shift = MODES[inp.mode]["price_shift"]
    b = inp.belief
    levels = [b.low * 0.98, b.best_guess, (b.best_guess + inp.ask) / 2, inp.ask * 0.99]
    # Never go backwards; when raising, move by at least 0.25% of list (not a single cent).
    floor_price = (inp.last_offer or 0) + max(0.01, round(inp.list_price * 0.0025, 2))
    prices = sorted({round(min(inp.ask, max(floor_price, p * shift)), 2) for p in levels})
    return [Offer(p, inp.quantity, pay) for p in prices for pay in (PAY_NOW, PAY_LATER)]


def _rollout(inp: SearchInput, pred: SupplierPredictor, offer: Offer, probs: dict,
             floor_std: float, ask: float, rnd: int, depth: int, rng: random.Random) -> float:
    """Play one sampled future from `offer` and return its dollar value."""
    walk_cost = MODES[inp.mode]["walk_cost_frac"] * inp.list_price * inp.quantity
    r = rng.random()
    if r < probs["accept"]:
        return deal_value(offer.price, offer.quantity, offer.pay_in_days, inp.list_price, inp.cash)
    if r < probs["accept"] + probs["walk"]:
        return -walk_cost
    # Supplier counters: concede part of the way toward its (terms-adjusted) floor.
    floor = floor_std * terms_factor(offer.pay_in_days)
    new_ask = round(ask - rng.choice(CONCESSION_RATES) * max(0.0, ask - floor), 2)
    if depth >= DEPTH:
        # Leaf: assume we can take the supplier's ask.
        return deal_value(new_ask, offer.quantity, offer.pay_in_days, inp.list_price, inp.cash)
    nxt = Offer(round((offer.price + new_ask) / 2, 2), offer.quantity, offer.pay_in_days)
    state = PredictState(floor_std, new_ask, inp.list_price, rnd + 1, inp.max_rounds, depth=depth)
    nxt_probs = pred.predict(state, [nxt])[0]
    return _rollout(inp, pred, nxt, nxt_probs, floor_std, new_ask, rnd + 1, depth + 1, rng)


def choose_move(inp: SearchInput, pred: SupplierPredictor, seed: int | None = None) -> dict:
    """Return {"best": Offer, "considered": [...top alternatives...], "timed_out": bool}."""
    start = time.monotonic()
    rng = random.Random(seed)
    cands = candidate_moves(inp)
    totals = {c: 0.0 for c in cands}
    accepts = {c: 0.0 for c in cands}
    n = 0
    timed_out = False
    for floor_std in inp.belief.sample(SAMPLES):
        if time.monotonic() - start > TIME_LIMIT_S:
            timed_out = True
            break
        state = PredictState(floor_std, inp.ask, inp.list_price, inp.round, inp.max_rounds,
                             depth=0, context=inp.context or {})
        probs = pred.predict(state, cands)           # one batched call per sampled supplier
        for c, p in zip(cands, probs):
            totals[c] += _rollout(inp, pred, c, p, floor_std, inp.ask, inp.round, 1, rng)
            accepts[c] += p["accept"]
        n += 1
    n = max(n, 1)
    ranked = sorted(cands, key=lambda c: -totals[c])
    considered = [
        {"price": c.price, "pay_in_days": c.pay_in_days,
         "expected_value": round(totals[c] / n, 2), "p_accept": round(accepts[c] / n, 2)}
        for c in ranked
    ]
    return {"best": ranked[0], "considered": considered[:5], "timed_out": timed_out,
            "elapsed_s": round(time.monotonic() - start, 3), "samples": n,
            "predictor": getattr(pred, "last_source", type(pred).__name__)}
