"""Supplier uAgent: wraps the rule-based supplier/policy.py.

Settings (optional, from .env): SUPPLIER_PERSONALITY, SUPPLIER_SEASON, SUPPLIER_RNG_SEED.
"""
import os

from uagents import Agent, Context

from agents.config import require_seed
from agents.messages import Accept, NegotiationStart, Offer, Reject
from supplier.policy import SupplierPolicy, make_secret, write_secret

supplier = Agent(
    name="dealroom-supplier",
    seed=require_seed("SUPPLIER_SEED"),
    description="Simulated packaging and bakery-goods supplier for the DealRoom demo.",
)

_session: dict = {}   # one negotiation at a time: {"buyer": address, "policy": SupplierPolicy, "quantity": int}


def _rng_seed() -> int | None:
    raw = os.environ.get("SUPPLIER_RNG_SEED", "").strip()
    return int(raw) if raw else None


@supplier.on_message(model=NegotiationStart, replies=Offer)
async def on_start(ctx: Context, sender: str, msg: NegotiationStart):
    """New negotiation: roll a secret floor and send the opening quote."""
    secret = make_secret(
        msg.list_price,
        personality=os.environ.get("SUPPLIER_PERSONALITY") or None,
        season=os.environ.get("SUPPLIER_SEASON") or None,
        seed=_rng_seed(),
    )
    write_secret(secret)   # for the end-of-demo reveal only
    policy = SupplierPolicy(secret)
    _session.update(buyer=sender, policy=policy, quantity=msg.quantity)
    ctx.logger.info(f"New negotiation: {msg.quantity} x {msg.item} ({secret.personality}, {secret.season})")
    opening = policy.opening(msg.quantity)
    await ctx.send(sender, Offer(price=opening["price"], quantity=msg.quantity,
                                 pay_in_days=opening["pay_in_days"], message=opening["message"]))


@supplier.on_message(model=Offer, replies={Offer, Accept, Reject})
async def on_offer(ctx: Context, sender: str, msg: Offer):
    """Answer a buyer offer using the rule-based policy."""
    if _session.get("buyer") != sender:
        await ctx.send(sender, Reject(reason="No open negotiation with you."))
        return
    reply = _session["policy"].respond(msg.price, msg.quantity, msg.pay_in_days)
    if reply["kind"] == "accept":
        await ctx.send(sender, Accept(price=reply["price"], pay_in_days=reply["pay_in_days"]))
        _session.clear()
    elif reply["kind"] == "reject":
        await ctx.send(sender, Reject(reason=reply["message"]))
        _session.clear()
    else:
        await ctx.send(sender, Offer(price=reply["price"], quantity=msg.quantity,
                                     pay_in_days=reply["pay_in_days"], message=reply["message"]))
