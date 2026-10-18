"""Simulated supplier uAgents, one per business in supplier/profiles.py.

Each agent wraps supplier/policy.py with its own private profile and keeps a
separate policy per negotiation_id, so negotiations never share state.
Settings (optional, from .env): SUPPLIER_RNG_SEED. Seeds derive from SUPPLIER_SEED.
"""
import itertools
import os

from uagents import Agent, Context

from agents.config import require_seed
from agents.messages import Accept, Cancel, Confirm, NegotiationStart, Offer, Reject, Withdraw
from supplier.policy import SupplierPolicy, secret_for_profile
from supplier.profiles import PROFILES, SupplierProfile

SECRETS_PATH = "supplier_secret.json"


def _rng_seed() -> int | None:
    raw = os.environ.get("SUPPLIER_RNG_SEED", "").strip()
    return int(raw) if raw else None


def make_supplier_agent(profile: SupplierProfile) -> Agent:
    """Build one supplier agent. Its seed is derived from SUPPLIER_SEED in .env."""
    agent = Agent(
        name=f"dealroom-supplier-{profile.id}",
        seed=f"{require_seed('SUPPLIER_SEED')}-{profile.id}",
        description=f"Simulated supplier ({profile.id}) for the DealRoom marketplace demo.",
    )
    sessions: dict[str, dict] = {}     # negotiation_id -> {"buyer", "policy", "request_id", "name"}
    tx = itertools.count(1)

    def next_tx() -> str:
        return f"TX-{profile.id[:3].upper()}-{next(tx):04d}"

    def ids(neg_id: str) -> dict:
        return {"request_id": sessions[neg_id]["request_id"], "negotiation_id": neg_id, "tx_id": next_tx()}

    async def send_reply(ctx: Context, neg_id: str, reply: dict) -> None:
        s = sessions[neg_id]
        if reply["kind"] == "accept":
            await ctx.send(s["buyer"], Accept(**ids(neg_id), price=reply["price"], quantity=reply["quantity"],
                                              pay_in_days=reply["pay_in_days"],
                                              deliver_in_days=reply.get("deliver_in_days")))
        elif reply["kind"] == "reject":
            await ctx.send(s["buyer"], Reject(**ids(neg_id), reason=reply["message"]))
            sessions.pop(neg_id, None)
        else:
            await ctx.send(s["buyer"], Offer(**ids(neg_id), price=reply["price"],
                                             quantity=reply.get("quantity", s["quantity"]),
                                             pay_in_days=reply["pay_in_days"],
                                             deliver_in_days=reply.get("deliver_in_days"),
                                             reliability=reply.get("reliability"), message=reply["message"]))

    @agent.on_message(model=NegotiationStart, replies=Offer)
    async def on_start(ctx: Context, sender: str, msg: NegotiationStart):
        secret = secret_for_profile(profile, msg.reference_price, seed=_rng_seed())
        policy = SupplierPolicy(secret, profile)
        name = profile.name or msg.vendor_name
        sessions[msg.negotiation_id] = {"buyer": sender, "policy": policy, "request_id": msg.request_id,
                                        "quantity": msg.quantity, "name": name}
        _write_secret(profile.id, name, secret)
        ctx.logger.info(f"{msg.negotiation_id}: quote request for {msg.quantity} x {msg.item}")
        await send_reply(ctx, msg.negotiation_id, policy.opening(msg.quantity, msg.unit))

    @agent.on_message(model=Offer, replies={Offer, Accept, Reject})
    async def on_offer(ctx: Context, sender: str, msg: Offer):
        s = sessions.get(msg.negotiation_id)
        if not s or s["buyer"] != sender:
            await ctx.send(sender, Reject(negotiation_id=msg.negotiation_id, tx_id=next_tx(),
                                          reason="No open negotiation with you."))
            return
        reply = s["policy"].respond(msg.price, msg.quantity, msg.pay_in_days, msg.deliver_in_days)
        await send_reply(ctx, msg.negotiation_id, reply)

    @agent.on_message(model=Confirm)
    async def on_confirm(ctx: Context, sender: str, msg: Confirm):
        s = sessions.get(msg.negotiation_id)
        if s and s["buyer"] == sender:
            s["policy"].confirm()
            ctx.logger.info(f"{msg.negotiation_id}: order confirmed, terms locked")

    @agent.on_message(model=Cancel)
    async def on_cancel(ctx: Context, sender: str, msg: Cancel):
        if sessions.get(msg.negotiation_id, {}).get("buyer") == sender:
            sessions.pop(msg.negotiation_id, None)
            ctx.logger.info(f"{msg.negotiation_id}: cancelled by buyer ({msg.reason})")

    @agent.on_message(model=Reject)
    async def on_buyer_reject(ctx: Context, sender: str, msg: Reject):
        if sessions.get(msg.negotiation_id, {}).get("buyer") == sender:
            sessions.pop(msg.negotiation_id, None)
            ctx.logger.info(f"{msg.negotiation_id}: buyer ended negotiation ({msg.reason})")

    @agent.on_interval(period=2.0)
    async def watch_capacity(ctx: Context):
        """React to judge disruptions: withdraw accepted deals we can no longer fill."""
        for neg_id, s in list(sessions.items()):
            reason = s["policy"].check_withdraw()
            if reason:
                await ctx.send(s["buyer"], Withdraw(**ids(neg_id), reason=reason))
                ctx.logger.info(f"{neg_id}: withdrew ({reason})")

    return agent


def _write_secret(profile_id: str, name: str, secret) -> None:
    """End-of-demo reveal only; never sent to the buyer."""
    import json
    from dataclasses import asdict
    try:
        data = json.load(open(SECRETS_PATH))
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    data[profile_id] = {"name": name, **asdict(secret)}
    with open(SECRETS_PATH, "w") as f:
        json.dump(data, f, indent=2)


suppliers = {pid: make_supplier_agent(p) for pid, p in PROFILES.items()}
