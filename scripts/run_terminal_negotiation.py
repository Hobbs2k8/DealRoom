"""Runs one full negotiation in the terminal: scout -> buyer vs. rule-based supplier.

Uses JevPredictor when TYPESAFE_API_KEY is set, else HeuristicPredictor. Example:
    python -m scripts.run_terminal_negotiation --personality bluffer --mode aggressive --seed 7
"""
import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from core.negotiator import BuyerNegotiator
from core.offers import describe_order
from core.predictor import make_predictor
from core.scout import best_opportunity, cash_context
from supplier.policy import PERSONALITIES, SupplierPolicy, make_secret, write_secret


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--company", default=os.environ.get("COMPANY_ID", "company-001"))
    p.add_argument("--personality", choices=PERSONALITIES)
    p.add_argument("--season", choices=("busy", "normal", "slow"))
    p.add_argument("--mode", choices=("passive", "balanced", "aggressive"), default="balanced")
    p.add_argument("--cash-floor", type=float, default=float(os.environ.get("CASH_FLOOR", 20000)))
    p.add_argument("--seed", type=int)
    p.add_argument("--predictor", choices=("auto", "heuristic", "jev"), default="auto",
                   help="auto = Jev if TYPESAFE_API_KEY is set, else heuristic")
    return p.parse_args()


def main():
    load_dotenv()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    args = parse_args()

    opp = best_opportunity(args.company)
    if not opp:
        print("Scout found nothing worth negotiating.")
        return
    cash = {**cash_context(args.company), "cash_floor": args.cash_floor}
    v = opp.vendor
    print(f"\n== SCOUT: {opp.company} ==")
    print(f"Target: {v.name}, {describe_order(v.typical_qty, v.top_item, v.unit, v.price_now)}")
    for r in opp.reasons:
        print(f"  - {r}")
    print(f"Cash ${cash['cash']:,.0f}, payroll next 14 days ${cash['payroll_next']:,.0f}, "
          f"owner floor ${cash['cash_floor']:,.0f}")

    secret = make_secret(v.price_now, args.personality, args.season, seed=args.seed)
    write_secret(secret)
    supplier = SupplierPolicy(secret)
    predictor = make_predictor(args.predictor)
    print(f"Predictor: {type(predictor).__name__}")
    buyer = BuyerNegotiator(opp, cash, predictor, mode=args.mode, seed=args.seed)

    print(f"\n== NEGOTIATION (mode={args.mode}) ==")
    opening = supplier.opening(buyer.quantity)
    print(f"Supplier opens: ${opening['price']:.2f}  \"{opening['message']}\"")
    buyer.observe(opening)

    while not buyer.done():
        move = buyer.next_offer()
        o = move["offer"]
        b = buyer.belief.summary()
        src = f"  [{buyer.last_predictor}]" if buyer.last_predictor else ""
        print(f"\nRound {buyer.round}{src}  belief floor ${b['low']:.2f}-${b['high']:.2f} "
              f"(best guess ${b['best_guess']:.2f})")
        for alt in buyer.last_considered[:3]:
            print(f"    considered ${alt['price']:.2f} pay {alt['pay_in_days']:>2}d  "
                  f"EV ${alt['expected_value']:>8,.0f}  p(accept) {alt['p_accept']:.2f}")
        print(f"  BUYER  -> ${o.price:.2f}, pay in {o.pay_in_days}d  \"{move['message']}\"")
        reply = supplier.respond(o.price, o.quantity, o.pay_in_days)
        price = f"${reply['price']:.2f}" if reply["price"] is not None else ""
        print(f"  SUPPLIER {reply['kind'].upper():6} {price}  \"{reply['message']}\"")
        buyer.observe(reply)

    print("\n== RESULT ==")
    if buyer.final:
        f = buyer.final
        print(f"Supplier accepted: {describe_order(f['quantity'], f['item'], f['unit'], f['price'])}, "
              f"pay in {f['pay_in_days']}d. Saves ${f['saved']:,.2f} vs ${f['list_price']:.2f}.")
        print("Waiting for owner approval (nothing is final until the owner approves).")
    else:
        print("No deal: the supplier walked away.")
    b = buyer.belief.summary()
    net30 = supplier.effective_floor(30)
    print(f"\nReveal: supplier base floor ${secret.floor:.2f}, ${net30:.2f} at net 30 after {secret.season} season "
          f"({secret.personality}, likes prepay: {secret.likes_prepay}).")
    print(f"Buyer's final guess of the net-30 floor: ${b['low']:.2f}-${b['high']:.2f} (best ${b['best_guess']:.2f})")


if __name__ == "__main__":
    main()
