"""Buyer negotiation session: one supplier, round by round.

Used directly by the terminal script, and once per supplier by core/market.py.
It knows nothing about transport: the caller passes supplier replies in and
sends offers out. Replies are dicts: {"kind": "offer"|"accept"|"reject",
"price", "pay_in_days", "message", optional "quantity", "deliver_in_days"}.
"""
from core import demo_state, writer
from core.belief import FloorBelief
from core.offers import Offer
from core.predictor import SupplierPredictor
from core.scout import Opportunity
from core.search import SearchInput, choose_move


class BuyerNegotiator:
    def __init__(self, opp: Opportunity, cash: dict, predictor: SupplierPredictor,
                 mode: str = "balanced", max_rounds: int = 6, seed: int | None = None,
                 write_demo_state: bool = True, vendor_name: str | None = None,
                 list_price: float | None = None):
        v = opp.vendor
        self.opp = opp
        self.vendor_name = vendor_name or v.name
        self.item = v.top_item
        self.unit = v.unit            # "unit" (per-item price) or "payment" (per-bill price)
        # This supplier's opening price (belief is built around it) vs. what we pay today.
        self.list_price = list_price or v.price_now
        self.baseline_price = v.price_now
        self.pay_options = (0, 45)
        self.deliver_in_days: int | None = None
        self.quantity = v.typical_qty
        self.cash = cash
        self.predictor = predictor
        self.mode = mode
        self.max_rounds = max_rounds
        self.seed = seed
        self.write_demo_state = write_demo_state
        self.belief = FloorBelief(self.list_price, seed=seed)
        self.round = 0
        self.ask = self.list_price
        self.prev_ask = None
        self.last_offer: Offer | None = None
        self.history: list[dict] = []
        self.last_considered: list[dict] = []
        self.last_predictor = ""
        self.status = "open"          # open | agreed | failed
        self.final: dict | None = None

    # ---- inputs ----------------------------------------------------------
    def observe(self, reply: dict) -> None:
        """Update belief and status from a supplier reply."""
        self.history.append({"round": self.round, "from": "supplier", **reply})
        kind = reply["kind"]
        if kind == "accept":
            self.belief.observe_accept(reply["price"], reply["pay_in_days"])
            self.status = "agreed"
            self.final = {
                "vendor": self.vendor_name, "item": self.item, "unit": self.unit,
                "quantity": reply.get("quantity", self.quantity),
                "price": reply["price"], "pay_in_days": reply["pay_in_days"],
                "deliver_in_days": reply.get("deliver_in_days"),
                "list_price": self.baseline_price,
                "saved": round((self.baseline_price - reply["price"]) * self.quantity, 2),
                "owner_approved": None,   # nothing is agreed until the owner approves
            }
        elif kind == "reject":
            if self.last_offer:
                self.belief.observe_reject(self.last_offer.price, self.last_offer.pay_in_days)
            self.status = "failed"
        else:  # counteroffer (or the opening quote)
            if self.last_offer:
                self.belief.observe_counter(self.last_offer.price, reply["price"],
                                            self.prev_ask, reply["pay_in_days"])
            self.prev_ask, self.ask = self.ask, reply["price"]
        self._save()

    # ---- outputs ---------------------------------------------------------
    def next_offer(self) -> dict:
        """Run the look-ahead search and return {"offer": Offer, "message": str}."""
        self.round += 1
        if self.round >= self.max_rounds:
            # Out of patience: take the supplier's current ask (they will accept it).
            pay = self.last_offer.pay_in_days if self.last_offer else self.pay_options[-1]
            best = Offer(self.ask, self.quantity, pay if pay in self.pay_options else self.pay_options[0],
                         self.deliver_in_days)
            self.last_considered = []
        else:
            result = choose_move(SearchInput(
                belief=self.belief, ask=self.ask,
                last_offer=self.last_offer.price if self.last_offer else None,
                list_price=self.list_price, quantity=self.quantity, round=self.round,
                max_rounds=self.max_rounds, cash=self.cash, mode=self.mode,
                context={"item": self.item, "quantity": self.quantity, "list_price": self.list_price,
                         "history": self.history[-8:]},
                pay_options=self.pay_options, baseline_price=self.baseline_price,
                deliver_in_days=self.deliver_in_days,
            ), self.predictor, seed=None if self.seed is None else self.seed + self.round)
            best = result["best"]
            self.last_considered = result["considered"]
            self.last_predictor = result["predictor"]
        self.last_offer = best
        reason = self._leverage() if self.round == 1 else "We're close; this works for us."
        msg = writer.offer_message(best.price, best.quantity, best.pay_in_days, self.item, reason, self.unit,
                                   best.deliver_in_days)
        self.history.append({"round": self.round, "from": "buyer", "kind": "offer", **best.to_dict(),
                             "message": msg})
        self._save()
        return {"offer": best, "message": msg}

    def done(self) -> bool:
        return self.status != "open"

    def _leverage(self) -> str:
        v = self.opp.vendor
        return (f"We've bought ${v.total_spend:,.0f} from you this year and paid every bill "
                f"within a few days of due.")

    def snapshot(self) -> dict:
        return {
            "company": self.opp.company, "vendor": self.vendor_name, "item": self.item,
            "unit": self.unit,
            "quantity": self.quantity, "list_price": self.list_price, "mode": self.mode,
            "round": self.round, "status": self.status, "offers": self.history,
            "belief": self.belief.summary(), "top_moves": self.last_considered,
            "predictor": self.last_predictor,
            "final_deal": self.final,
        }

    def _save(self) -> None:
        if self.write_demo_state:
            demo_state.write(self.snapshot())
