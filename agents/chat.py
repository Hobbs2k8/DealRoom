"""Fetch Agent Chat Protocol (ACP) for the buyer, so the owner can talk to it in ASI:One.

Every ChatMessage is acknowledged with a ChatAcknowledgement. Replies go back as
ChatMessage/TextContent. Commands are plain text:
  scan | negotiate | passive / balanced / aggressive | approve | decline | status | help
"""
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

from agents.buyer import MODES, controller

chat_proto = Protocol(spec=chat_protocol_spec)

HELP = (
    "I'm your DealRoom buyer. I read your QuickBooks payables, find a bill worth negotiating, "
    "and haggle with the supplier for you. Nothing is agreed without your approval.\n"
    "Commands: 'scan' (find an opportunity), 'negotiate' (start), "
    "'passive' / 'balanced' / 'aggressive' (how hard to push), "
    "'approve' / 'decline' (final deal), 'status'."
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


def _status() -> str:
    n = controller.negotiation
    if not n:
        return f"No negotiation yet. Mode: {controller.mode}. Say 'scan' to start."
    b = n.belief.summary()
    line = (f"{n.opp.vendor.name}: round {n.round}, status {n.status}. "
            f"Their ask ${n.ask:.2f}; my guess of their floor ${b['low']:.2f}-${b['high']:.2f}.")
    if n.final:
        approved = {None: "waiting for your approval", True: "approved", False: "declined"}
        line += f" Deal at ${n.final['price']:.2f} ({approved[n.final['owner_approved']]})."
    return line


async def handle_command(ctx: Context, text: str) -> None:
    """Map the owner's plain-text message to a controller action."""
    t = text.lower().strip()
    words = set(t.replace(",", " ").replace(".", " ").split())
    if words & set(MODES):
        mode = next(m for m in MODES if m in words)
        await send_to_owner(ctx, controller.set_mode(mode))
        if not ({"negotiate", "start"} & words):
            return
    if {"approve", "approved"} & words or t in ("yes", "y"):
        await controller.decide(ctx, True)
    elif {"decline", "declined"} & words or t in ("no", "n"):
        await controller.decide(ctx, False)
    elif {"negotiate", "start", "haggle"} & words:
        await controller.negotiate(ctx)
    elif {"scan", "find", "opportunity", "opportunities", "bills"} & words:
        await controller.scan(ctx)
    elif "status" in words:
        await send_to_owner(ctx, _status())
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
