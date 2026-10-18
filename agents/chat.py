"""Fetch Agent Chat Protocol (ACP) for the buyer, so the owner can talk to it in ASI:One.

Every ChatMessage is acknowledged with a ChatAcknowledgement. Replies go back as
ChatMessage/TextContent. Commands are plain text:
  scan | negotiate | passive / balanced / aggressive | status | compare | audit |
  floor <dollars> | approve [supplier] | decline | help
Judge-only demo control (simulation, not something the buyer can do in real life):
  judge disrupt <supplier> <capacity> | judge restore <supplier>
"""
import re

from datetime import datetime, timezone
from uuid import uuid4

from uagents import Context, Protocol
from uagents_core.contrib.protocols.chat import (
    ChatAcknowledgement,
    ChatMessage,
    EndSessionContent,
    StartSessionContent,
    TextContent,
    chat_protocol_spec,
)

from agents.buyer import MODES, controller, format_ranking
from supplier import controls          # judge control only; the buyer never reads supplier state
from supplier.profiles import PROFILES

chat_proto = Protocol(spec=chat_protocol_spec)

HELP = (
    "I'm your DealRoom buyer. I read your QuickBooks payables, find a bill worth negotiating, "
    "get quotes from several supplier agents (all simulated in this demo) and negotiate with each. "
    "Nothing is bought without your approval.\n"
    "Commands: 'scan', 'negotiate', 'passive' / 'balanced' / 'aggressive', 'status', 'compare', "
    "'audit', 'floor 25000' (cash floor), 'approve' (the recommended deal) or 'approve <supplier>', "
    "'decline'.\nJudge controls: 'judge disrupt prairie 100' (a supplier loses capacity), "
    "'judge restore prairie'. Suppliers: " + ", ".join(PROFILES) + "."
)

_owner = {"address": None}   # the last ASI:One user who talked to us


def text_message(text: str) -> ChatMessage:
    return ChatMessage(
        timestamp=datetime.now(timezone.utc),
        msg_id=uuid4(),
        content=[TextContent(type="text", text=text)],
    )


async def send_to_owner(ctx: Context, text: str) -> None:
    """Route the controller's owner-facing updates into the chat."""
    ctx.logger.info(f"[to owner] {text}")
    if _owner["address"]:
        await ctx.send(_owner["address"], text_message(text))


controller.notify_owner = send_to_owner


async def judge_command(ctx: Context, t: str) -> None:
    """Demo-only world events, applied to the supplier side. The buyer learns only from replies."""
    m = re.match(r"judge\s+(disrupt|restore)\s+(\w+)(?:\s+(\d+))?", t)
    if not m or m.group(2) not in PROFILES:
        await send_to_owner(ctx, "Judge controls: 'judge disrupt <supplier> <capacity>' or "
                                 f"'judge restore <supplier>'. Suppliers: {', '.join(PROFILES)}.")
        return
    action, sid, cap = m.group(1), m.group(2), m.group(3)
    if action == "disrupt":
        controls.set_capacity(sid, int(cap or 0))
        await send_to_owner(ctx, f"[judge] {sid} now has capacity {int(cap or 0)}. Its agent will react on "
                                 f"its next reply, or withdraw an accepted deal it can no longer fill.")
    else:
        controls.set_capacity(sid, None)
        await send_to_owner(ctx, f"[judge] {sid} capacity restored.")


async def handle_command(ctx: Context, text: str) -> None:
    """Map the owner's plain-text message to a controller action."""
    t = text.lower().strip()
    words = set(t.replace(",", " ").replace(".", " ").split())
    if t.startswith("judge"):
        await judge_command(ctx, t)
        return
    floor = re.match(r"(?:cash\s+)?floor\s+\$?([\d,]+)", t)
    if floor:
        await controller.set_floor(ctx, float(floor.group(1).replace(",", "")))
        return
    if words & set(MODES):
        mode = next(m for m in MODES if m in words)
        await send_to_owner(ctx, controller.set_mode(mode))
        if not ({"negotiate", "start"} & words):
            return
    if {"approve", "approved"} & words or t in ("yes", "y"):
        hint = re.sub(r"^(approve|approved)\s*", "", t).strip()
        await controller.decide(ctx, True, hint)
    elif {"decline", "declined"} & words or t in ("no", "n"):
        await controller.decide(ctx, False)
    elif {"negotiate", "start", "haggle"} & words:
        await controller.negotiate(ctx)
    elif {"scan", "find", "opportunity", "opportunities", "bills"} & words:
        await controller.scan(ctx)
    elif "status" in words:
        await send_to_owner(ctx, controller.status_text())
    elif {"compare", "offers", "ranking"} & words:
        await send_to_owner(ctx, format_ranking(controller.market) if controller.market else "No offers yet.")
    elif {"audit", "trail", "why"} & words:
        await send_to_owner(ctx, controller.audit_text())
    else:
        await send_to_owner(ctx, HELP)


@chat_proto.on_message(ChatMessage)
async def on_chat(ctx: Context, sender: str, msg: ChatMessage):
    # Always acknowledge first.
    await ctx.send(sender, ChatAcknowledgement(timestamp=datetime.now(timezone.utc),
                                               acknowledged_msg_id=msg.msg_id))
    _owner["address"] = sender
    for item in msg.content:
        if isinstance(item, StartSessionContent):
            await send_to_owner(ctx, HELP)
        elif isinstance(item, TextContent):
            ctx.logger.info(f"[from owner] {item.text}")
            await handle_command(ctx, item.text)
        elif isinstance(item, EndSessionContent):
            ctx.logger.info("Owner ended the chat session")


@chat_proto.on_message(ChatAcknowledgement)
async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    ctx.logger.debug(f"Owner acknowledged {msg.acknowledged_msg_id}")
