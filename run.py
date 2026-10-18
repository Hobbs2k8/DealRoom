"""Runs the buyer and supplier agents together in one Bureau.

    python run.py           # agents start and wait for the owner (chat comes in step 4)
    python run.py --auto    # buyer scans and negotiates on startup (local demo)
"""
import argparse
import os

import agents.config  # noqa: F401  (loads .env and SSL certs before uagents builds its HTTP clients)
from uagents import Bureau, Context

from agents.buyer import buyer, controller
from agents.supplier import supplier

PORT = int(os.environ.get("BUREAU_PORT", "8000"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--auto", action="store_true", help="scan and negotiate on startup")
    parser.add_argument("--mode", choices=("passive", "balanced", "aggressive"), default="balanced")
    args = parser.parse_args()

    controller.supplier_address = supplier.address
    controller.mode = args.mode

    if args.auto:
        @buyer.on_event("startup")
        async def auto_start(ctx: Context):
            await controller.scan(ctx)
            await controller.negotiate(ctx)

    print(f"buyer    {buyer.address}")
    print(f"supplier {supplier.address}")
    bureau = Bureau(agents=[buyer, supplier], port=PORT,
                    endpoint=f"http://127.0.0.1:{PORT}/submit")
    bureau.run()


if __name__ == "__main__":
    main()
