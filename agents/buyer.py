"""Buyer uAgent: scouts the books, negotiates with the supplier agent, reports to the owner.

The negotiation logic is core/negotiator.py. This file only moves messages.
Owner-facing text goes through `notify_owner`, which logs for now; step 4 points
it at the ASI:One chat.
"""
import asyncio
import os
from typing import Awaitable, Callable

from uagents import Agent, Context

from agents.config import require_seed
from agents.messages import Accept, NegotiationStart, Offer, Reject
from core import demo_state, writer
from core.negotiator import BuyerNegotiator
from core.offers import describe_order
from core.predictor import make_predictor
from core.scout import best_opportunity, cash_context

COMPANY_ID = os.environ.get("COMPANY_ID", "company-001")
CASH_FLOOR = float(os.environ.get("CASH_FLOOR", "20000"))
MODES = ("passive", "balanced", "aggressive")

buyer = Agent(
    name="dealroom-buyer",
    seed=require_seed("BUYER_SEED"),
    mailbox=True,   # reachable from ASI:One through Agentverse
    description="DealRoom: negotiating purchasing agent for small businesses. Reads QuickBooks bills, finds supplier deals worth renegotiating, haggles on price and payment terms, and asks the owner to approve every deal.",
    readme_path=os.path.join(os.path.dirname(__file__), "buyer_readme.md"),
    publish_agent_details=True,
)


class BuyerController:
    """Holds the buyer's state between messages (one negotiation at a time)."""

    def __init__(self):
        self.supplier_address: str | None = None
        self.mode = "balanced"
        self.opportunity = None
        self.negotiation: BuyerNegotiator | None = None
        # Where owner-facing text goes. Replaced by the chat sender in step 4.
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
        o = self.opportunity
        v = o.vendor
        reasons = "\n".join(f"- {r}" for r in o.reasons)
        await self.notify_owner(ctx, (
            f"Best opportunity for {o.company}: {v.name}, "
            f"{describe_order(v.typical_qty, v.top_item, v.unit, v.price_now)}.\n{reasons}\nSay 'negotiate' to start (mode: {self.mode})."))

    def set_mode(self, mode: str) -> str:
        if mode not in MODES:
            return f"Mode must be one of: {', '.join(MODES)}."
        self.mode = mode
        return f"Mode set to {mode}."

    async def negotiate(self, ctx: Context) -> None:
        """Start a negotiation with the supplier agent."""
        if self.negotiation and not self.negotiation.done():
            await self.notify_owner(ctx, "A negotiation is already running.")
            return
        if not self.supplier_address:
            await self.notify_owner(ctx, "No supplier agent is connected.")
            return
        if not self.opportunity:
            self.opportunity = best_opportunity(COMPANY_ID)
        cash = {**cash_context(COMPANY_ID), "cash_floor": CASH_FLOOR}
        self.negotiation = BuyerNegotiator(self.opportunity, cash, make_predictor(), mode=self.mode)
        n = self.negotiation
        await ctx.send(self.supplier_address,
                       NegotiationStart(item=n.item, quantity=n.quantity, list_price=n.list_price))
        await self.notify_owner(ctx, f"Negotiating with {self.opportunity.vendor.name} "
                                     f"for {describe_order(n.quantity, n.item, n.unit, n.list_price)} "
                                     f"({self.mode} mode)...")

    async def decide(self, ctx: Context, approved: bool) -> None:
        """Owner approves or declines the supplier-accepted deal."""
        n = self.negotiation
        if not n or not n.final or n.final["owner_approved"] is not None:
            await self.notify_owner(ctx, "There's no deal waiting for approval.")
            return
        n.final["owner_approved"] = approved
        demo_state.write(n.snapshot())
        f = n.final
        if approved:
            await self.notify_owner(ctx, f"Approved. Ordering "
                                         f"{describe_order(f['quantity'], f['item'], f['unit'], f['price'])}, "
                                         f"paid in {f['pay_in_days']} days. "
                                         f"You save ${f['saved']:,.2f}.")
        else:
            await self.notify_owner(ctx, "Declined. Nothing was ordered.")

    # ---- supplier replies ------------------------------------------------
    async def on_supplier_reply(self, ctx: Context, reply: dict) -> None:
        """Feed a supplier reply to the negotiator and send the next offer if still open."""
        n = self.negotiation
        if not n or n.done():
            ctx.logger.warning("Supplier reply with no open negotiation; ignoring")
            return
        n.observe(reply)
        if n.status == "agreed":
            f = n.final
            facts = (f"{f['vendor']} accepted "
                     f"{describe_order(f['quantity'], f['item'], f['unit'], f['price'])} "
                     f"(was ${f['list_price']:,.2f}), paid in {f['pay_in_days']} days. "
                     f"That saves ${f['saved']:,.2f}. Reply 'approve' or 'decline'.")
            await self.notify_owner(ctx, await asyncio.to_thread(writer.owner_message, facts))
            return
        if n.status == "failed":
            await self.notify_owner(ctx, f"The supplier walked away: {reply['message']} Nothing was agreed.")
            return
        # Search can take up to 2 s (longer with Jev); keep the agent's event loop free.
        move = await asyncio.to_thread(n.next_offer)
        o = move["offer"]
        b = n.belief.summary()
        ctx.logger.info(f"Round {n.round}: offer ${o.price:.2f} pay {o.pay_in_days}d "
                        f"(floor guess ${b['low']:.2f}-${b['high']:.2f})")
        pay = "pay now" if o.pay_in_days == 0 else f"pay in {o.pay_in_days} days"
        await self.notify_owner(ctx, f"Round {n.round}: they asked ${reply['price']:.2f}. "
                                     f"I'm offering ${o.price:.2f}, {pay}. "
                                     f"(My guess of their floor: ${b['low']:.2f}-${b['high']:.2f}.)")
        await ctx.send(self.supplier_address, Offer(price=o.price, quantity=o.quantity,
                                                    pay_in_days=o.pay_in_days, message=move["message"]))


controller = BuyerController()


@buyer.on_message(model=Offer, replies=Offer)
async def on_offer(ctx: Context, sender: str, msg: Offer):
    ctx.logger.info(f"Supplier offers ${msg.price:.2f} pay {msg.pay_in_days}d: {msg.message}")
    await controller.on_supplier_reply(ctx, {"kind": "offer", "price": msg.price,
                                             "pay_in_days": msg.pay_in_days, "message": msg.message})


@buyer.on_message(model=Accept)
async def on_accept(ctx: Context, sender: str, msg: Accept):
    ctx.logger.info(f"Supplier ACCEPTS ${msg.price:.2f} pay {msg.pay_in_days}d")
    await controller.on_supplier_reply(ctx, {"kind": "accept", "price": msg.price,
                                             "pay_in_days": msg.pay_in_days, "message": ""})


@buyer.on_message(model=Reject)
async def on_reject(ctx: Context, sender: str, msg: Reject):
    ctx.logger.info(f"Supplier REJECTS: {msg.reason}")
    await controller.on_supplier_reply(ctx, {"kind": "reject", "price": None,
                                             "pay_in_days": None, "message": msg.reason})
