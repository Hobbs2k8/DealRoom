"""Runs the marketplace in one process: the buyer negotiates with all three simulated
suppliers in parallel (no uAgents, no network). Good for checking outcomes quickly.

    python -m scripts.run_market
    python -m scripts.run_market --disrupt prairie=200      # judge: Prairie drops to 200 units
    python -m scripts.run_market --cash-floor 103000        # paying now becomes infeasible
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from core.market import MarketSession
from core.predictor import make_predictor
from core.scout import best_opportunity, cash_context
from supplier import controls
from supplier.policy import SupplierPolicy, secret_for_profile
from supplier.profiles import PROFILES


def deliver(session: MarketSession, policies: dict, outgoing: list[dict], quiet: bool) -> None:
    """Hand buyer messages to the in-process suppliers and feed replies back, until quiet."""
    queue = list(outgoing)
    while queue:
        msg = queue.pop(0)
        pol = policies[msg["to"]]
        if msg["kind"] == "start":
            reply = pol.opening(msg["quantity"], msg["unit"])
        elif msg["kind"] == "offer":
            reply = pol.respond(msg["price"], msg["quantity"], msg["pay_in_days"], msg["deliver_in_days"])
        elif msg["kind"] == "confirm":
            pol.confirm()
            continue
        else:   # reject / cancel from the buyer: supplier just stops
            continue
        if not quiet:
            name = session.legs[msg["negotiation_id"]].name
            price = f"${reply['price']:,.2f}" if reply.get("price") is not None else ""
            print(f"  {name[:34]:34} {reply['kind']:7} {price:>10}  {reply.get('message', '')[:70]}")
        queue += session.on_reply(msg["negotiation_id"], reply)


def print_ranking(session: MarketSession) -> None:
    print("\n== COMPARISON ==")
    for r in session.ranking():
        if r.get("total") is not None:
            mark = "OK " if r["feasible"] else "NO "
            print(f"  {mark}{r['supplier'][:34]:34} {r['order']}, pay {r['pay_in_days']}d, "
                  f"day {r['deliver_in_days']}, effective ${r['effective_cost']:,.0f}  ({r['why']})")
        else:
            print(f"  NO {r['supplier'][:34]:34} {r['status']}: {r['why']}")


def main():
    load_dotenv()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--company", default=os.environ.get("COMPANY_ID", "company-001"))
    p.add_argument("--need-by", type=int, default=int(os.environ.get("NEED_BY_DAYS", 7)))
    p.add_argument("--cash-floor", type=float, default=float(os.environ.get("CASH_FLOOR", 20000)))
    p.add_argument("--mode", choices=("passive", "balanced", "aggressive"), default="balanced")
    p.add_argument("--disrupt", action="append", default=[], metavar="SUPPLIER=CAPACITY",
                   help="judge control, e.g. prairie=200 (applied before the run)")
    p.add_argument("--disrupt-after-agree", metavar="SUPPLIER=CAPACITY",
                   help="judge control applied after deals are agreed, before approval")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()

    controls.reset()
    for d in args.disrupt:
        sid, cap = d.split("=")
        controls.set_capacity(sid, int(cap))

    opp = best_opportunity(args.company)
    cash = {**cash_context(args.company), "cash_floor": args.cash_floor}
    keys = list(PROFILES)
    session = MarketSession(opp, cash, [{"id": k, "name": PROFILES[k].name} for k in keys],
                            lambda: make_predictor(), need_by_days=args.need_by, mode=args.mode, seed=args.seed)
    policies = {k: SupplierPolicy(secret_for_profile(PROFILES[k], opp.vendor.price_now, seed=args.seed + i),
                                  PROFILES[k]) for i, k in enumerate(keys)}

    print(f"== REQUEST {session.request_id} (simulated suppliers) ==")
    print(f"{opp.company}: {session.quantity} x {session.item}, needed within {args.need_by} days, "
          f"cash floor ${args.cash_floor:,.0f}")
    deliver(session, policies, session.start(), args.quiet)
    print_ranking(session)

    if args.disrupt_after_agree:
        sid, cap = args.disrupt_after_agree.split("=")
        controls.set_capacity(sid, int(cap))
        print(f"\n== JUDGE: {sid} capacity -> {cap} ==")
        for leg in session.legs.values():
            reason = policies[leg.supplier_id].check_withdraw()
            if reason:
                print(f"  {leg.name} withdraws: {reason}")
                session.on_reply(leg.negotiation_id, {"kind": "withdraw", "message": reason})
        print_ranking(session)

    best = session.recommended()
    print("\n== RECOMMENDATION ==")
    print(f"  {best['supplier']}: {best['order']}" if best else "  No feasible deal.")
    if best:
        out, text = session.approve()
        deliver(session, policies, out, True)
        print(f"  Owner approves -> {text}")
    print(f"\nAudit trail: {len(session.audit)} entries in demo_state.json")
    controls.reset()


if __name__ == "__main__":
    main()
