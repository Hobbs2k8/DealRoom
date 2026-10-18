"""Runs the buyer and supplier agents together in one Bureau.

    python run.py           # agents start and wait for the owner to chat via ASI:One
    python run.py --auto    # buyer scans and negotiates on startup (local demo)
"""
import argparse
import os
from urllib.parse import quote

import agents.config  # noqa: F401  (loads .env and SSL certs before uagents builds its HTTP clients)
from uagents import Bureau, Context

from agents.buyer import buyer, controller
from agents.chat import chat_proto
from agents.supplier import supplier

PORT = int(os.environ.get("BUREAU_PORT", "8000"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--auto", action="store_true", help="scan and negotiate on startup")
    parser.add_argument("--mode", choices=("passive", "balanced", "aggressive"), default="balanced")
    args = parser.parse_args()

    buyer.include(chat_proto, publish_manifest=True)
    controller.supplier_address = supplier.address
    controller.mode = args.mode

    if args.auto:
        @buyer.on_event("startup")
        async def auto_start(ctx: Context):
            await controller.scan(ctx)
            await controller.negotiate(ctx)

    print(f"buyer    {buyer.address}")
    print(f"supplier {supplier.address}")
    inspector = (f"https://agentverse.ai/inspect/?uri={quote(f'http://127.0.0.1:{PORT}', safe='')}"
                 f"&address={buyer.address}")
    print("\nConnect the buyer to Agentverse (one time): open this link, click Connect, choose Mailbox:")
    print(f"  {inspector}")
    print("Then find 'dealroom-buyer' in ASI:One (or chat from its Agentverse page).\n")
    bureau = Bureau(agents=[buyer, supplier], port=PORT,
                    endpoint=f"http://127.0.0.1:{PORT}/submit")
    bureau.run()


if __name__ == "__main__":
    main()
