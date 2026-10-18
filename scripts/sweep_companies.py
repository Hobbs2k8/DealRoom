"""Runs the scout and one headless negotiation for every company in data/.

Checks that the pipeline works across all business types, not just the bakery.
Needs the full dataset: ./scripts/fetch_data.sh
    python -m scripts.sweep_companies            # summary table
    python -m scripts.sweep_companies --json out.json
"""
import argparse
import json
import os
import statistics
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.data import DATA_DIR
from core.negotiator import BuyerNegotiator
from core.offers import describe_order
from core.predictor import HeuristicPredictor
from core.scout import best_opportunity, cash_context
from supplier.policy import SupplierPolicy, make_secret


def run_one(cid: str, cash_floor: float, seed: int) -> dict:
    """Scout one company and negotiate against a seeded supplier. Never raises."""
    row = {"id": cid}
    try:
        opp = best_opportunity(cid)
        if not opp:
            return {**row, "result": "no opportunity"}
        v = opp.vendor
        row.update(company=opp.company, vendor=v.name, kind=v.kind,
                   order=describe_order(v.typical_qty, v.top_item, v.unit, v.price_now))
        cash = {**cash_context(cid), "cash_floor": cash_floor}
        supplier = SupplierPolicy(make_secret(v.price_now, seed=seed))
        buyer = BuyerNegotiator(opp, cash, HeuristicPredictor(), seed=seed, write_demo_state=False)
        buyer.observe(supplier.opening(buyer.quantity))
        while not buyer.done():
            o = buyer.next_offer()["offer"]
            buyer.observe(supplier.respond(o.price, o.quantity, o.pay_in_days))
        row["result"] = buyer.status
        if buyer.final:
            row.update(saved=buyer.final["saved"], rounds=buyer.round, pay_in_days=buyer.final["pay_in_days"])
    except Exception as e:   # report, keep going
        row.update(result="error", error=f"{type(e).__name__}: {e}")
    return row


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cash-floor", type=float, default=20000)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--json", help="write every row to this file")
    args = p.parse_args()

    meta = {c["company_id"]: c for c in json.load(open(os.path.join(DATA_DIR, "index.json")))}
    ids = sorted(c for c in meta if os.path.isdir(os.path.join(DATA_DIR, c)))
    rows = []
    for cid in ids:
        row = {**run_one(cid, args.cash_floor, args.seed), "profile": meta[cid]["profile"]}
        rows.append(row)
        print(f"{cid}  {row['result']:<14} {row.get('kind', ''):<8} {row.get('order', row.get('error', ''))[:70]}")

    ok = [r for r in rows if r["result"] == "agreed"]
    print(f"\n{len(ok)}/{len(rows)} companies reached a supplier-accepted deal")
    print("results:", dict(Counter(r["result"] for r in rows)))
    print("deal type:", dict(Counter(r.get("kind") for r in ok)))
    if ok:
        print(f"median saving ${statistics.median(r['saved'] for r in ok):,.0f}")
    if args.json:
        with open(args.json, "w") as f:
            json.dump(rows, f, indent=1)


if __name__ == "__main__":
    main()
