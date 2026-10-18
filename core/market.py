"""Marketplace session: one purchase request, negotiated with several suppliers in parallel.

Plain Python, no transport. The caller (buyer agent or an in-process script)
sends the returned outgoing messages and feeds supplier replies back in.

- Every request, negotiation, and message gets a mock transaction ID.
- Each supplier gets its own BuyerNegotiator ("leg"): its own belief, history and
  status. A reply is routed by negotiation_id, so one supplier's message can
  never change another supplier's negotiation.
- Only the purchase request and the buyer's offers go to suppliers. The ledger,
  cash balance and cash floor never leave this object.
- The recommended deal is the cheapest *feasible* one after a reliability risk
  charge: full quantity, delivered by the deadline, cash floor respected.
- Nothing is final until the owner approves one deal; the others are cancelled.
"""
import itertools
import time
from dataclasses import dataclass, field

from core import demo_state
from core.negotiator import BuyerNegotiator
from core.offers import describe_order
from core.scout import Opportunity
from core.score import cash_ok

SUPPLIER_TIMEOUT_S = 30.0       # a supplier that hasn't answered in this long is timed out
APPROVAL_TIMEOUT_S = 15 * 60.0  # owner has this long to approve before offers lapse
RISK_WEIGHT = 1.0               # risk charge = (1 - reliability) x total x RISK_WEIGHT

_counter = itertools.count(1)


def new_id(prefix: str) -> str:
    """Mock transaction IDs, unique within a run: REQ-0001, NEG-0002, TX-0003."""
    return f"{prefix}-{next(_counter):04d}"


@dataclass
class Leg:
    """One supplier's negotiation inside the request."""
    negotiation_id: str
    supplier_id: str            # how the caller addresses this supplier (agent address or profile id)
    name: str
    neg: BuyerNegotiator | None = None
    status: str = "requested"   # requested | negotiating | agreed | infeasible | rejected |
                                # withdrawn | timed_out | confirmed | cancelled
    reason: str = ""            # why it ended this way, for the audit trail
    offered_quantity: int | None = None
    deliver_in_days: int | None = None
    reliability: float | None = None
    asked_delivery: bool = False
    awaiting_since: float = field(default_factory=time.monotonic)

    @property
    def awaiting_reply(self) -> bool:
        return self.status in ("requested", "negotiating")


class MarketSession:
    def __init__(self, opp: Opportunity, cash: dict, suppliers: list[dict], predictor_factory,
                 need_by_days: int = 7, mode: str = "balanced", max_rounds: int = 6,
                 seed: int | None = None, write_demo_state: bool = True):
        """suppliers: [{"id": address-or-key, "name": display name or "" for the incumbent}]"""
        self.opp = opp
        self.cash = cash
        self.need_by_days = need_by_days
        self.mode = mode
        self.max_rounds = max_rounds
        self.seed = seed
        self.predictor_factory = predictor_factory
        self.write_demo_state = write_demo_state
        v = opp.vendor
        self.item, self.unit, self.quantity, self.reference_price = v.top_item, v.unit, v.typical_qty, v.price_now
        self.request_id = new_id("REQ")
        self.legs: dict[str, Leg] = {}
        for s in suppliers:
            leg = Leg(new_id("NEG"), s["id"], s["name"] or v.name)
            self.legs[leg.negotiation_id] = leg
        self.audit: list[dict] = []
        self.approved: str | None = None       # negotiation_id the owner approved
        self.declined = False
        self.all_done_at: float | None = None

    # ---- audit -------------------------------------------------------------
    def _log(self, frm: str, to: str, kind: str, summary: str, leg: Leg | None = None,
             reason: str = "") -> str:
        tx = new_id("TX")
        self.audit.append({"tx_id": tx, "t": round(time.time(), 1), "from": frm, "to": to,
                           "negotiation_id": leg.negotiation_id if leg else None,
                           "kind": kind, "summary": summary, "reason": reason})
        return tx

    def _out(self, leg: Leg, kind: str, summary: str, note: str = "", **payload) -> dict:
        """Build one outgoing message to a supplier and record it (note = why, for the audit)."""
        tx = self._log("buyer", leg.name, kind, summary, leg, note)
        leg.awaiting_since = time.monotonic()
        return {"to": leg.supplier_id, "kind": kind, "request_id": self.request_id,
                "negotiation_id": leg.negotiation_id, "tx_id": tx, **payload}

    # ---- start -------------------------------------------------------------
    def start(self) -> list[dict]:
        """Send the same request to every supplier. Shares only what the owner authorized:
        item, quantity, deadline, and today's price as a reference."""
        self._log("buyer", "all suppliers", "request",
                  f"{describe_order(self.quantity, self.item, self.unit, self.reference_price)}, "
                  f"needed within {self.need_by_days} days")
        out = []
        for leg in self.legs.values():
            out.append(self._out(leg, "start", "request for quote", item=self.item, quantity=self.quantity,
                                 unit=self.unit, need_by_days=self.need_by_days,
                                 reference_price=self.reference_price, vendor_name=leg.name))
        self._save()
        return out

    # ---- supplier replies --------------------------------------------------
    def on_reply(self, negotiation_id: str, reply: dict) -> list[dict]:
        """Route one supplier reply to its own leg and return what to send next."""
        leg = self.legs.get(negotiation_id)
        if not leg:
            self._log("unknown", "buyer", "ignored", f"reply for unknown negotiation {negotiation_id}")
            return []
        kind = reply["kind"]
        price = f"${reply['price']:,.2f}" if reply.get("price") is not None else ""
        self._log(leg.name, "buyer", kind, f"{kind} {price}".strip(), leg, reply.get("message", ""))
        if leg.status in ("confirmed", "cancelled", "timed_out", "infeasible", "rejected", "withdrawn") \
                and kind != "withdraw":
            return []   # late message for a finished negotiation: logged, ignored
        out: list[dict] = []
        if kind == "withdraw":
            out = self._on_withdraw(leg, reply)
        elif kind == "reject":
            leg.status, leg.reason = "rejected", reply.get("message", "supplier walked away")
            if leg.neg:
                leg.neg.observe(reply)
        elif kind == "accept":
            out = self._on_accept(leg, reply)
        else:
            out = self._on_offer(leg, reply)
        self._after_change()
        return out

    def _ensure_negotiator(self, leg: Leg, reply: dict) -> BuyerNegotiator:
        if leg.neg is None:
            leg.neg = BuyerNegotiator(
                self.opp, self.cash, self.predictor_factory(), mode=self.mode,
                max_rounds=self.max_rounds, write_demo_state=False, vendor_name=leg.name,
                list_price=reply["price"],
                seed=None if self.seed is None else self.seed + len(self.audit),
            )
        return leg.neg

    def _on_offer(self, leg: Leg, reply: dict) -> list[dict]:
        neg = self._ensure_negotiator(leg, reply)
        leg.status = "negotiating"
        leg.offered_quantity = reply.get("quantity", self.quantity)
        leg.deliver_in_days = reply.get("deliver_in_days", leg.deliver_in_days)
        if reply.get("reliability") is not None:
            leg.reliability = reply["reliability"]
        neg.observe(reply)

        # Hard constraint 1: quantity is firm.
        if leg.offered_quantity < self.quantity:
            return [self._end(leg, "infeasible",
                              f"can only supply {leg.offered_quantity} of {self.quantity} (quantity is firm)")]
        # Hard constraint 2: delivery deadline. Ask once (a bounded counter); if they can't, stop.
        why = f"floor guess ${neg.belief.low:,.2f}-${neg.belief.high:,.2f}"
        if leg.deliver_in_days is not None and leg.deliver_in_days > self.need_by_days:
            if leg.asked_delivery:
                return [self._end(leg, "infeasible",
                                  f"earliest delivery day {leg.deliver_in_days} misses the day-{self.need_by_days} deadline")]
            leg.asked_delivery = True
            neg.deliver_in_days = self.need_by_days
            why = f"they quoted delivery on day {leg.deliver_in_days}; asking for day {self.need_by_days}"
        # Payment terms the supplier insists on narrow what we can offer from now on.
        last = neg.last_offer
        if last and reply["pay_in_days"] != last.pay_in_days:
            neg.pay_options = (reply["pay_in_days"],)
            why = f"they require payment in {reply['pay_in_days']} days"
        move = neg.next_offer()
        o = move["offer"]
        return [self._out(leg, "offer", f"counter ${o.price:,.2f}, pay in {o.pay_in_days}d"
                          + (f", deliver by day {o.deliver_in_days}" if o.deliver_in_days is not None else ""),
                          why, price=o.price, quantity=o.quantity, pay_in_days=o.pay_in_days,
                          deliver_in_days=o.deliver_in_days, message=move["message"])]

    def _on_accept(self, leg: Leg, reply: dict) -> list[dict]:
        neg = leg.neg
        last = neg.last_offer if neg else None
        # A deal exists only if the supplier accepted the exact terms we offered.
        if not last or round(reply["price"], 2) != round(last.price, 2) \
                or reply.get("quantity", last.quantity) != last.quantity \
                or reply["pay_in_days"] != last.pay_in_days:
            return [self._end(leg, "rejected", "supplier 'accepted' terms we never offered")]
        neg.observe(reply)
        leg.status = "agreed"
        leg.deliver_in_days = reply.get("deliver_in_days", leg.deliver_in_days)
        leg.reason = f"supplier accepted ${reply['price']:,.2f}"
        return []

    def _on_withdraw(self, leg: Leg, reply: dict) -> list[dict]:
        if leg.status == "confirmed":
            leg.reason = "supplier tried to withdraw after confirmation; terms stay locked"
            return []
        was = leg.status
        leg.status, leg.reason = "withdrawn", reply.get("message", "supplier withdrew")
        if self.approved == leg.negotiation_id:
            self.approved = None
        self._log("buyer", "owner", "reevaluate", f"{leg.name} withdrew while {was}; re-ranking", leg)
        return []

    def _end(self, leg: Leg, status: str, reason: str) -> dict:
        """Close a leg on our side and tell that supplier why."""
        leg.status, leg.reason = status, reason
        return self._out(leg, "reject", f"stop: {reason}", reason, reason=reason)

    # ---- owner / time -------------------------------------------------------
    def check_timeouts(self, now: float | None = None, timeout: float = SUPPLIER_TIMEOUT_S) -> list[dict]:
        """Time out suppliers that went quiet; lapse offers if the owner never decides."""
        now = now or time.monotonic()
        out = []
        for leg in self.legs.values():
            if leg.awaiting_reply and now - leg.awaiting_since > timeout:
                out.append(self._end(leg, "timed_out", f"no reply within {int(timeout)} s"))
        if self.all_done_at and not self.approved and not self.declined \
                and now - self.all_done_at > APPROVAL_TIMEOUT_S:
            out += self.decline("owner did not approve in time")
        if out:
            self._after_change()
        return out

    def set_cash_floor(self, floor: float) -> None:
        self.cash = {**self.cash, "cash_floor": floor}
        for leg in self.legs.values():
            if leg.neg:
                leg.neg.cash = self.cash
        self._log("owner", "buyer", "constraint", f"cash floor set to ${floor:,.0f}")
        self._save()

    def approve(self, negotiation_id: str | None = None) -> tuple[list[dict], str]:
        """Owner approves one deal (default: the recommended one). Others are cancelled."""
        ranked = self.ranking()
        feasible = [r for r in ranked if r["feasible"]]
        if negotiation_id is None:
            if not feasible:
                return [], "There's no feasible deal to approve."
            negotiation_id = feasible[0]["negotiation_id"]
        row = next((r for r in ranked if r["negotiation_id"] == negotiation_id), None)
        if not row or not row["feasible"]:
            return [], "That deal isn't available or breaks one of your constraints."
        leg = self.legs[negotiation_id]
        leg.status, self.approved = "confirmed", negotiation_id
        leg.neg.final["owner_approved"] = True
        out = [self._out(leg, "confirm", f"owner approved {row['order']}", "owner approval")]
        for other in self.legs.values():
            if other is not leg and other.status in ("requested", "negotiating", "agreed"):
                other.status, other.reason = "cancelled", f"owner chose {leg.name}"
                out.append(self._out(other, "cancel", "request closed", other.reason, reason=other.reason))
        self._save()
        delivery = f", delivered by day {row['deliver_in_days']}" if self.unit == "unit" else ""
        return out, f"Approved: {leg.name}, {row['order']}, paid in {row['pay_in_days']} days{delivery}."

    def decline(self, reason: str = "owner declined") -> list[dict]:
        self.declined = True
        out = []
        for leg in self.legs.values():
            if leg.status in ("requested", "negotiating", "agreed"):
                leg.status, leg.reason = "cancelled", reason
                out.append(self._out(leg, "cancel", "request closed", reason, reason=reason))
        self._save()
        return out

    # ---- comparison ---------------------------------------------------------
    def done(self) -> bool:
        return not any(leg.awaiting_reply for leg in self.legs.values())

    def ranking(self) -> list[dict]:
        """Every supplier, with its outcome, feasibility and why. Feasible deals first, best first."""
        rows = []
        for leg in self.legs.values():
            row = {"negotiation_id": leg.negotiation_id, "supplier": leg.name, "status": leg.status,
                   "reliability": leg.reliability, "deliver_in_days": leg.deliver_in_days,
                   "feasible": False, "why": leg.reason}
            f = leg.neg.final if leg.neg else None
            if leg.status in ("agreed", "confirmed") and f:
                total = round(f["price"] * f["quantity"], 2)
                risk = round((1 - (leg.reliability or 1.0)) * total * RISK_WEIGHT, 2)
                problems = []
                if f["quantity"] < self.quantity:
                    problems.append(f"only {f['quantity']} of {self.quantity}")
                if leg.deliver_in_days is not None and leg.deliver_in_days > self.need_by_days:
                    problems.append(f"delivers day {leg.deliver_in_days}, after day {self.need_by_days}")
                if not cash_ok(total, f["pay_in_days"], self.cash):
                    problems.append("paying now would take cash below your floor before payroll")
                row.update(price=f["price"], quantity=f["quantity"], pay_in_days=f["pay_in_days"],
                           total=total, risk_charge=risk, effective_cost=round(total + risk, 2),
                           saved=f["saved"], order=describe_order(f["quantity"], self.item, self.unit, f["price"]),
                           feasible=not problems,
                           why="; ".join(problems) if problems else
                           f"meets quantity, day-{self.need_by_days} deadline and cash floor; "
                           f"{(leg.reliability or 1):.0%} reliable adds ${risk:,.0f} risk")
            rows.append(row)
        return sorted(rows, key=lambda r: (not r["feasible"], r.get("effective_cost", float("inf"))))

    def recommended(self) -> dict | None:
        best = self.ranking()
        return best[0] if best and best[0]["feasible"] else None

    # ---- state ---------------------------------------------------------------
    def _after_change(self) -> None:
        if self.done() and self.all_done_at is None:
            self.all_done_at = time.monotonic()
        self._save()

    def snapshot(self) -> dict:
        return {
            "simulated": True,
            "request_id": self.request_id, "company": self.opp.company,
            "request": {"item": self.item, "unit": self.unit, "quantity": self.quantity,
                        "need_by_days": self.need_by_days, "reference_price": self.reference_price},
            "constraints": {"quantity_firm": True, "need_by_days": self.need_by_days,
                            "cash_floor": self.cash["cash_floor"]},
            "mode": self.mode,
            "negotiations": [
                {"negotiation_id": l.negotiation_id, "supplier": l.name, "status": l.status, "reason": l.reason,
                 "reliability": l.reliability, "deliver_in_days": l.deliver_in_days,
                 "round": l.neg.round if l.neg else 0,
                 "belief": l.neg.belief.summary() if l.neg else None,
                 "offers": l.neg.history if l.neg else [],
                 "top_moves": l.neg.last_considered if l.neg else [],
                 "final_deal": l.neg.final if l.neg else None}
                for l in self.legs.values()],
            "ranking": self.ranking(),
            "approved_negotiation": self.approved,
            "audit": self.audit,
        }

    def _save(self) -> None:
        if self.write_demo_state:
            demo_state.write(self.snapshot())
