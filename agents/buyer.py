"""Buyer uAgent: scouts the books, runs a request across several supplier agents, reports to the owner.

The marketplace logic is core/market.py (one BuyerNegotiator per supplier). This
file only moves messages and turns state changes into owner updates.
Owner-facing text goes through `notify_owner`, which agents/chat.py points at ASI:One.
"""
import asyncio
import os
from typing import Awaitable, Callable

from uagents import Agent, Context

from agents.config import require_seed
from agents.messages import Accept, Cancel, Confirm, NegotiationStart, Offer, Reject, Withdraw
from core.market import MarketSession
from core.offers import describe_order
from core.predictor import make_predictor
from core.scout import best_opportunity, cash_context

COMPANY_ID = os.environ.get("COMPANY_ID", "company-001")
CASH_FLOOR = float(os.environ.get("CASH_FLOOR", "20000"))
NEED_BY_DAYS = int(os.environ.get("NEED_BY_DAYS", "7"))
MODES = ("passive", "balanced", "aggressive")

buyer = Agent(
    name="dealroom-buyer",
    seed=require_seed("BUYER_SEED"),
    mailbox=True,   # reachable from ASI:One through Agentverse
    description="DealRoom: negotiating purchasing agent for small businesses. Reads QuickBooks bills, gets quotes from several suppliers, haggles on price and terms, and asks the owner to approve every deal.",
    readme_path=os.path.join(os.path.dirname(__file__), "buyer_readme.md"),
    publish_agent_details=True,
)


def format_ranking(market: MarketSession) -> str:
    """Owner-facing comparison: feasible deals first, then why the others are out."""
    lines = []
    for i, r in enumerate(market.ranking()):
        if r.get("total") is not None:
            tag = "Recommended" if i == 0 and r["feasible"] else ("OK" if r["feasible"] else "Not feasible")
            lines.append(f"{tag}: {r['supplier']}: {r['order']}, pay in {r['pay_in_days']} days, "
                         f"delivery day {r['deliver_in_days']}, total ${r['total']:,.2f} ({r['why']}).")
        else:
            lines.append(f"Out: {r['supplier']}: {r['status'].replace('_', ' ')}: {r['why'].rstrip('.')}.")
    return "\n".join(lines)


class BuyerController:
    """Holds the buyer's state between messages (one request at a time)."""

    def __init__(self):
        self.suppliers: list[dict] = []     # [{"id": agent address, "name": display name or ""}]
        self.mode = "balanced"
        self.cash_floor = CASH_FLOOR
        self.opportunity = None
        self.market: MarketSession | None = None
        self._reported: dict[str, str] = {}   # negotiation_id -> last status told to the owner
        self._compared = False
        self.notify_owner: Callable[[Context, str], Awaitable[None]] = self._log_to_owner

    async def _log_to_owner(self, ctx: Context, text: str) -> None:
        ctx.logger.info(f"[to owner] {text}")

    # ---- owner commands --------------------------------------------------
    async def scan(self, ctx: Context) -> None:
        """Find the best negotiation opportunity and explain why."""
        self.opportunity = best_opportunity(COMPANY_ID)
        if not self.opportunity:
            await self.notify_owner(ctx, "I didn't find a bill worth negotiating right now.")
            return
        o, v = self.opportunity, self.opportunity.vendor
        reasons = "\n".join(f"- {r}" for r in o.reasons)
        await self.notify_owner(ctx, (
            f"Best opportunity for {o.company}: {v.name}, "
            f"{describe_order(v.typical_qty, v.top_item, v.unit, v.price_now)}.\n{reasons}\n"
            f"Say 'negotiate' and I'll get quotes from {len(self.suppliers)} suppliers "
            f"(mode: {self.mode}, needed within {NEED_BY_DAYS} days)."))

    def set_mode(self, mode: str) -> str:
        if mode not in MODES:
            return f"Mode must be one of: {', '.join(MODES)}."
        self.mode = mode
        return f"Mode set to {mode}."

    async def set_floor(self, ctx: Context, floor: float) -> None:
        self.cash_floor = floor
        if self.market:
            self.market.set_cash_floor(floor)
            await self.notify_owner(ctx, f"Cash floor set to ${floor:,.0f}. Re-checked every deal:\n"
                                         f"{format_ranking(self.market)}")
        else:
            await self.notify_owner(ctx, f"Cash floor set to ${floor:,.0f}.")

    async def negotiate(self, ctx: Context) -> None:
        """Send one request to every supplier agent and negotiate with each in parallel."""
        if self.market and not self.market.done():
            await self.notify_owner(ctx, "A request is already running. Say 'status' to see it.")
            return
        if not self.suppliers:
            await self.notify_owner(ctx, "No supplier agents are connected.")
            return
        if not self.opportunity:
            self.opportunity = best_opportunity(COMPANY_ID)
        cash = {**cash_context(COMPANY_ID), "cash_floor": self.cash_floor}
        self.market = MarketSession(self.opportunity, cash, self.suppliers, make_predictor,
                                    need_by_days=NEED_BY_DAYS, mode=self.mode)
        self._reported, self._compared = {}, False
        m = self.market
        await self.notify_owner(ctx, (
            f"Request {m.request_id}: {describe_order(m.quantity, m.item, m.unit, m.reference_price)}, "
            f"needed within {m.need_by_days} days. Sent to {len(m.legs)} simulated supplier agents; "
            f"negotiating with each in parallel ({self.mode} mode). Suppliers see only the request, "
            f"never your books or cash floor."))
        await self.send(ctx, m.start())

    async def decide(self, ctx: Context, approved: bool, supplier_hint: str = "") -> None:
        """Owner approves (the recommended deal, or one named supplier) or declines."""
        m = self.market
        if not m or not m.done() or m.approved or m.declined:
            await self.notify_owner(ctx, "There's no set of deals waiting for your decision.")
            return
        if not approved:
            await self.send(ctx, m.decline())
            await self.notify_owner(ctx, "Declined. Every supplier was told the request is closed. Nothing was ordered.")
            return
        neg_id = None
        if supplier_hint:
            neg_id = next((l.negotiation_id for l in m.legs.values()
                           if supplier_hint.lower() in l.name.lower()), None)
            if not neg_id:
                await self.notify_owner(ctx, f"I don't have a supplier matching '{supplier_hint}'.")
                return
        out, text = m.approve(neg_id)
        await self.send(ctx, out)
        await self.notify_owner(ctx, text + (" The other suppliers were told the request is closed." if out else ""))

    # ---- transport ---------------------------------------------------------
    async def send(self, ctx: Context, outgoing: list[dict]) -> None:
        """Turn MarketSession's outgoing dicts into uAgents messages."""
        for o in outgoing:
            ids = {k: o[k] for k in ("request_id", "negotiation_id", "tx_id")}
            if o["kind"] == "start":
                msg = NegotiationStart(**ids, item=o["item"], quantity=o["quantity"], unit=o["unit"],
                                       need_by_days=o["need_by_days"], reference_price=o["reference_price"],
                                       vendor_name=o["vendor_name"])
            elif o["kind"] == "offer":
                msg = Offer(**ids, price=o["price"], quantity=o["quantity"], pay_in_days=o["pay_in_days"],
                            deliver_in_days=o["deliver_in_days"], message=o["message"])
            elif o["kind"] == "confirm":
                msg = Confirm(**ids)
            elif o["kind"] == "cancel":
                msg = Cancel(**ids, reason=o["reason"])
            else:
                msg = Reject(**ids, reason=o["reason"])
            await ctx.send(o["to"], msg)

    async def on_supplier_reply(self, ctx: Context, sender: str, negotiation_id: str, reply: dict) -> None:
        m = self.market
        leg = m.legs.get(negotiation_id) if m else None
        if not leg or leg.supplier_id != sender:
            ctx.logger.warning(f"Ignoring reply for unknown negotiation {negotiation_id}")
            return
        # Search can take up to 2 s (longer with Jev); keep the agent's event loop free.
        out = await asyncio.to_thread(m.on_reply, negotiation_id, reply)
        await self.send(ctx, out)
        await self.report(ctx)

    async def tick(self, ctx: Context) -> None:
        if self.market:
            out = self.market.check_timeouts()
            if out:
                await self.send(ctx, out)
                await self.report(ctx)

    async def report(self, ctx: Context) -> None:
        """Tell the owner when a supplier's negotiation ends, and compare once all are in."""
        m = self.market
        for leg in m.legs.values():
            if leg.status == self._reported.get(leg.negotiation_id) or leg.awaiting_reply:
                continue
            self._reported[leg.negotiation_id] = leg.status
            if leg.status == "agreed":
                f = leg.neg.final
                await self.notify_owner(ctx, f"{leg.name} accepted "
                                             f"{describe_order(f['quantity'], m.item, m.unit, f['price'])}, "
                                             f"pay in {f['pay_in_days']} days, delivery day {leg.deliver_in_days}.")
            elif leg.status == "withdrawn" and self._compared:
                await self.notify_owner(ctx, f"{leg.name} withdrew: {leg.reason}\nRe-evaluated:\n"
                                             f"{format_ranking(m)}\n"
                                             + ("Reply 'approve' for the new recommendation or 'decline'."
                                                if m.recommended() else "No feasible deal is left."))
            elif leg.status in ("infeasible", "rejected", "timed_out", "withdrawn"):
                await self.notify_owner(ctx, f"{leg.name}: {leg.status.replace('_', ' ')}: {leg.reason.rstrip('.')}.")
        if m.done() and not self._compared:
            self._compared = True
            best = m.recommended()
            tail = (f"\nReply 'approve' to buy from {best['supplier']} on exactly these terms, "
                    f"'approve <supplier>' for another feasible one, or 'decline'."
                    if best else "\nNo deal meets your constraints, so I won't recommend one.")
            await self.notify_owner(ctx, f"All suppliers have answered request {m.request_id}:\n"
                                         f"{format_ranking(m)}{tail}")

    # ---- owner views ---------------------------------------------------------
    def status_text(self) -> str:
        m = self.market
        if not m:
            return f"No request yet. Mode {self.mode}, cash floor ${self.cash_floor:,.0f}. Say 'scan' to start."
        lines = [f"Request {m.request_id} ({'done' if m.done() else 'negotiating'}):"]
        for l in m.legs.values():
            b = l.neg.belief.summary() if l.neg else None
            guess = f", floor guess ${b['low']:,.2f}-${b['high']:,.2f}" if b else ""
            ask = f", their ask ${l.neg.ask:,.2f}" if l.neg else ""
            lines.append(f"- {l.name} [{l.negotiation_id}]: {l.status}{ask}{guess}")
        return "\n".join(lines)

    def audit_text(self, last: int = 14) -> str:
        m = self.market
        if not m:
            return "Nothing to audit yet."
        rows = [f"{a['tx_id']} {a['from']} -> {a['to']}: {a['summary']}" + (f" ({a['reason']})" if a['reason'] else "")
                for a in m.audit[-last:]]
        return f"Audit trail for {m.request_id} (last {len(rows)} of {len(m.audit)}; full trail in demo_state.json):\n" \
               + "\n".join(rows)


controller = BuyerController()


@buyer.on_message(model=Offer, replies={Offer, Reject})
async def on_offer(ctx: Context, sender: str, msg: Offer):
    await controller.on_supplier_reply(ctx, sender, msg.negotiation_id, {
        "kind": "offer", "price": msg.price, "quantity": msg.quantity, "pay_in_days": msg.pay_in_days,
        "deliver_in_days": msg.deliver_in_days, "reliability": msg.reliability, "message": msg.message})


@buyer.on_message(model=Accept)
async def on_accept(ctx: Context, sender: str, msg: Accept):
    await controller.on_supplier_reply(ctx, sender, msg.negotiation_id, {
        "kind": "accept", "price": msg.price, "quantity": msg.quantity, "pay_in_days": msg.pay_in_days,
        "deliver_in_days": msg.deliver_in_days, "message": ""})


@buyer.on_message(model=Reject)
async def on_reject(ctx: Context, sender: str, msg: Reject):
    await controller.on_supplier_reply(ctx, sender, msg.negotiation_id, {
        "kind": "reject", "price": None, "pay_in_days": None, "message": msg.reason})


@buyer.on_message(model=Withdraw)
async def on_withdraw(ctx: Context, sender: str, msg: Withdraw):
    await controller.on_supplier_reply(ctx, sender, msg.negotiation_id, {
        "kind": "withdraw", "price": None, "pay_in_days": None, "message": msg.reason})


@buyer.on_interval(period=5.0)
async def check_timeouts(ctx: Context):
    await controller.tick(ctx)
