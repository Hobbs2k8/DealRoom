"""Local check of the buyer's chat protocol without ASI:One.

A fake owner agent runs in the same Bureau as the buyer and supplier and sends
plain-text ChatMessages: help, scan, aggressive + negotiate, status, approve.
    python -m scripts.chat_smoke_test
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents.config  # noqa: F401  (env + certs before uagents)
from uagents import Agent, Bureau, Context, Protocol
from uagents_core.contrib.protocols.chat import ChatAcknowledgement, ChatMessage, TextContent, chat_protocol_spec

from agents.buyer import buyer, controller
from agents.chat import chat_proto, text_message
from agents.supplier import supplier

SCRIPT = [(2, "hello"), (3, "scan"), (5, "aggressive, negotiate"), (14, "status"), (16, "approve")]

owner = Agent(name="fake-owner", seed="dealroom fake owner for local chat smoke test")
owner_proto = Protocol(spec=chat_protocol_spec)
acks = []


@owner_proto.on_message(ChatMessage)
async def on_reply(ctx: Context, sender: str, msg: ChatMessage):
    await ctx.send(sender, ChatAcknowledgement(timestamp=msg.timestamp, acknowledged_msg_id=msg.msg_id))
    for c in msg.content:
        if isinstance(c, TextContent):
            print(f"\n<<< BUYER: {c.text}", flush=True)


@owner_proto.on_message(ChatAcknowledgement)
async def on_ack(ctx: Context, sender: str, msg: ChatAcknowledgement):
    acks.append(msg.acknowledged_msg_id)


owner.include(owner_proto)


@owner.on_event("startup")
async def run_script(ctx: Context):
    import asyncio
    elapsed = 0
    for at, text in SCRIPT:
        await asyncio.sleep(at - elapsed)
        elapsed = at
        print(f"\n>>> OWNER: {text}", flush=True)
        await ctx.send(buyer.address, text_message(text))
    await asyncio.sleep(2)
    print(f"\nAcknowledgements received: {len(acks)} of {len(SCRIPT)}", flush=True)
    os._exit(0)


if __name__ == "__main__":
    buyer.include(chat_proto, publish_manifest=False)
    controller.supplier_address = supplier.address
    Bureau(agents=[buyer, supplier, owner], port=8001, endpoint="http://127.0.0.1:8001/submit").run()
