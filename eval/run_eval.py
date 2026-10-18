"""Evaluation: does the look-ahead buyer beat simpler approaches, on real QuickBooks bills?

For every company in data/ that the scout finds an opportunity for, we negotiate against
many seeded suppliers and compare buyers on the SAME suppliers:

  split    rule-based: open at 85% of the ask, split the difference each round (net 45)
  llm      an LLM picks every offer from the negotiation history (needs ANTHROPIC_API_KEY)
  search   our buyer: belief over the floor + look-ahead search, heuristic predictor
  jev      our buyer with the Jev predictor (needs TYPESAFE_API_KEY)

Supplier types:
  built     stubborn, desperate, bluffer, walker   (used while building the buyer)
  held-out  noisy, hardball, deadline              (defined only here; the buyer never saw them)

Run (full data: ./scripts/fetch_data.sh first):
  python -m eval.run_eval                         # split + search, all companies, 10 seeds per type
  python -m eval.run_eval --seeds 30 --buyers split search
  python -m eval.run_eval --buyers split search llm --llm-limit 40
  python -m eval.run_eval --buyers split search jev --companies company-001

Writes eval/results.csv (one row per negotiation) and eval/summary.md (tables for the pitch).
"""
import argparse
import csv
import json
import os
import random
import re
import statistics
import sys
import time
import zlib
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

from core import writer
from core.data import DATA_DIR
from core.negotiator import BuyerNegotiator
from core.predictor import HeuristicPredictor, make_predictor
from core.scout import best_opportunity, cash_context
from supplier import policy as sp
from supplier.policy import SupplierPolicy, make_secret

BUILT = ["stubborn", "desperate", "bluffer", "walker"]
HELD_OUT = ["noisy", "hardball", "deadline"]
SEASON_MULT = {"busy": 1.05, "normal": 1.0, "slow": 0.95}
OUT_DIR = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------- suppliers
class NoisyPolicy(SupplierPolicy):
    """Concedes an unpredictable amount each round (held-out)."""

    def __init__(self, secret, rng):
        super().__init__(secret)
        self.rng = rng

    def respond(self, price, quantity, pay_in_days, deliver_in_days=None):
        p = self.s.personality
        base = sp.CONCEDE[p]
        sp.CONCEDE[p] = base * self.rng.uniform(0.2, 2.0)
        try:
            return super().respond(price, quantity, pay_in_days, deliver_in_days)
        finally:
            sp.CONCEDE[p] = base


def make_supplier(kind: str, list_price: float, seed: int):
    """Returns (policy, true floor at standard terms incl. season)."""
    rng = random.Random(seed)
    if kind in BUILT:
        secret = make_secret(list_price, kind, seed=seed)
        pol = SupplierPolicy(secret)
    elif kind == "noisy":
        secret = make_secret(list_price, "bluffer", seed=seed)
        pol = NoisyPolicy(secret, rng)
    elif kind == "hardball":          # floor only 3-10% under list, never budges much
        secret = make_secret(list_price, "stubborn", seed=seed, floor_range=(0.90, 0.97))
        pol = SupplierPolicy(secret)
    elif kind == "deadline":          # concedes fast but only has 3 rounds of patience
        secret = make_secret(list_price, "desperate", seed=seed)
        secret.max_rounds = 3
        pol = SupplierPolicy(secret)
    else:
        raise ValueError(kind)
    true_floor = secret.floor * SEASON_MULT[secret.season]
    return pol, true_floor


# ---------------------------------------------------------------- buyers
class SplitBuyer:
    """Open at 85% of the ask, then split the difference. Always net 45."""
    name = "split"

    def __init__(self, opp, cash, **_):
        self.q = opp.vendor.typical_qty
        self.last = None
        self.moves = 0

    def first(self, ask):
        return round(ask * 0.85, 2), 45

    def next(self, ask, last_reply):
        if self.last is None:
            price = round(ask * 0.85, 2)
        elif ask - self.last <= ask * 0.01:
            price = ask
        else:
            price = round((self.last + ask) / 2, 2)
        self.last = price
        return price, 45


class LLMBuyer:
    """An LLM chooses each offer from the history. Same information our buyer gets."""
    name = "llm"

    def __init__(self, opp, cash, model=None, **_):
        import anthropic
        self.client = anthropic.Anthropic(timeout=30, max_retries=1)
        self.model = model or os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
        v = opp.vendor
        self.setup = (f"You are a purchasing agent for {opp.company}. You are negotiating with "
                      f"{v.name} for {v.typical_qty} x {v.top_item}. Current price ${v.price_now:.2f} "
                      f"per unit. We spent ${v.total_spend:,.0f} with them this year and pay on time. "
                      f"Cash on hand ${cash['cash']:,.0f}; payroll due soon ${cash['payroll_next']:,.0f}; "
                      f"owner's minimum cash balance ${cash['cash_floor']:,.0f}. Paying now (0 days) may "
                      f"earn a discount; paying in 45 days keeps cash. Goal: lowest price without the "
                      f"supplier walking away and without breaking the cash floor.")
        self.history = []
        self.tokens_in = self.tokens_out = 0
        self.moves = 0

    def next(self, ask, last_reply):
        self.history.append(f"Supplier: ${ask:.2f} per unit ({last_reply.get('message', '')})")
        prompt = (self.setup + "\n\nHistory:\n" + "\n".join(self.history) +
                  '\n\nReply with ONLY JSON: {"price": <per-unit price>, "pay_in_days": 0 or 45}')
        resp = self.client.messages.create(model=self.model, max_tokens=200,
                                           messages=[{"role": "user", "content": prompt}])
        self.tokens_in += resp.usage.input_tokens
        self.tokens_out += resp.usage.output_tokens
        text = "".join(b.text for b in resp.content if b.type == "text")
        m = re.search(r"\{.*\}", text, re.S)
        try:
            d = json.loads(m.group(0))
            price, pay = float(d["price"]), int(d["pay_in_days"])
        except Exception:
            price, pay = ask, 45
        pay = 0 if pay == 0 else 45
        price = round(min(price, ask), 2)
        self.history.append(f"Us: ${price:.2f}, pay in {pay} days")
        return price, pay


class SearchBuyer:
    """Our buyer (core/negotiator.py) with a chosen predictor."""

    def __init__(self, opp, cash, predictor, seed, name):
        self.name = name
        self.neg = BuyerNegotiator(opp, cash, predictor, seed=seed, write_demo_state=False)

    def observe(self, reply):
        self.neg.observe(reply)

    def next(self, ask, last_reply):
        o = self.neg.next_offer()["offer"]
        return o.price, o.pay_in_days


# ---------------------------------------------------------------- one negotiation
def negotiate(buyer, supplier, quantity, max_rounds=12):
    """Run buyer vs supplier. Returns dict with outcome and timing."""
    reply = supplier.opening(quantity)
    if isinstance(buyer, SearchBuyer):
        buyer.observe(reply)
    think_s, rounds = 0.0, 0
    while reply["kind"] == "offer" and rounds < max_rounds:
        rounds += 1
        t0 = time.perf_counter()
        price, pay = buyer.next(reply["price"], reply)
        think_s += time.perf_counter() - t0
        reply = supplier.respond(price, quantity, pay)
        if isinstance(buyer, SearchBuyer):
            buyer.observe(reply)
            if buyer.neg.done():
                break
    deal = reply["kind"] == "accept"
    return {"deal": deal, "price": reply["price"] if deal else None,
            "pay_in_days": reply["pay_in_days"] if deal else None,
            "rounds": rounds, "ms_per_move": 1000 * think_s / max(rounds, 1)}


# ---------------------------------------------------------------- main loop
def companies(only):
    ids = sorted(d for d in os.listdir(DATA_DIR) if d.startswith("company-"))
    return [c for c in ids if not only or c in only]


def main():
    load_dotenv()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--buyers", nargs="+", default=["split", "search"],
                    choices=["split", "llm", "search", "jev"])
    ap.add_argument("--seeds", type=int, default=10, help="suppliers per type per company")
    ap.add_argument("--companies", nargs="*")
    ap.add_argument("--cash-floor", type=float, default=20000)
    ap.add_argument("--llm-limit", type=int, default=40, help="max LLM negotiations (cost control)")
    ap.add_argument("--llm-model")
    ap.add_argument("--llm-price-in", type=float, default=0.0, help="$ per 1M input tokens, for cost column")
    ap.add_argument("--llm-price-out", type=float, default=0.0, help="$ per 1M output tokens")
    args = ap.parse_args()

    writer._claude = lambda prompt: None          # templates only: we measure decisions, not prose
    rows, llm_used = [], 0
    jev_pred = make_predictor("jev") if "jev" in args.buyers else None
    cos = companies(args.companies)
    print(f"{len(cos)} companies, buyers {args.buyers}, {args.seeds} suppliers per type each")

    for ci, cid in enumerate(cos, 1):
        try:
            opp = best_opportunity(cid)
        except Exception as e:
            print(f"  {cid}: scout error {e}")
            continue
        if not opp:
            continue
        cash = {**cash_context(cid), "cash_floor": args.cash_floor}
        lp, q = opp.vendor.price_now, opp.vendor.typical_qty
        for kind in BUILT + HELD_OUT:
            for s in range(args.seeds):
                seed = zlib.crc32(f"{cid}|{kind}|{s}".encode()) % 10**9   # same suppliers every run
                for bname in args.buyers:
                    if bname == "llm" and llm_used >= args.llm_limit:
                        continue
                    supplier, true_floor = make_supplier(kind, lp, seed)
                    if bname == "split":
                        buyer = SplitBuyer(opp, cash)
                    elif bname == "llm":
                        buyer = LLMBuyer(opp, cash, model=args.llm_model)
                        llm_used += 1
                    elif bname == "search":
                        buyer = SearchBuyer(opp, cash, HeuristicPredictor(), seed, "search")
                    else:
                        buyer = SearchBuyer(opp, cash, jev_pred, seed, "jev")
                    try:
                        r = negotiate(buyer, supplier, q)
                    except Exception as e:
                        print(f"  {cid} {kind} {bname}: error {type(e).__name__}: {e}")
                        continue
                    saved_pct = (lp - r["price"]) / lp if r["deal"] else 0.0
                    row = {"company": cid, "industry": opp.company, "supplier": kind,
                           "set": "built" if kind in BUILT else "held-out", "buyer": bname, "seed": seed,
                           "list_price": lp, "quantity": q, "true_floor": round(true_floor, 2), **r,
                           "saved_pct": round(saved_pct, 4),
                           "saved_dollars": round((lp - r["price"]) * q, 2) if r["deal"] else 0.0}
                    if isinstance(buyer, SearchBuyer):
                        row["floor_guess"] = buyer.neg.belief.best_guess
                        row["floor_err_pct"] = round(abs(buyer.neg.belief.best_guess - true_floor) / lp, 4)
                    if isinstance(buyer, LLMBuyer):
                        row["tokens_in"], row["tokens_out"] = buyer.tokens_in, buyer.tokens_out
                        row["cost_usd"] = round((buyer.tokens_in * args.llm_price_in +
                                                 buyer.tokens_out * args.llm_price_out) / 1e6, 5)
                    rows.append(row)
        print(f"  [{ci}/{len(cos)}] {cid} {opp.company}: {opp.vendor.top_item} @ ${lp:.2f} x {q}")

    if not rows:
        print("No results. Is data/ populated?")
        return
    write_outputs(rows)


def write_outputs(rows):
    keys = sorted({k for r in rows for k in r})
    with open(os.path.join(OUT_DIR, "results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)

    def stats(rs):
        out = {"n": len(rs),
               "saved": statistics.mean(r["saved_pct"] for r in rs),
               "deal": sum(r["deal"] for r in rs) / len(rs),
               "rounds": statistics.mean(r["rounds"] for r in rs),
               "ms": statistics.median(r["ms_per_move"] for r in rs),
               "dollars": sum(r["saved_dollars"] for r in rs)}
        errs = [r["floor_err_pct"] for r in rs if "floor_err_pct" in r]
        out["floor_err"] = statistics.mean(errs) if errs else None
        costs = [r["cost_usd"] for r in rs if "cost_usd" in r]
        out["cost"] = statistics.mean(costs) if costs else 0.0
        return out

    lines = ["# DealRoom evaluation", "",
             f"{len(rows)} negotiations, {len({r['company'] for r in rows})} companies. "
             "Savings = % below the current price, counting failed deals as 0%.", ""]
    hdr = "| buyer | negotiations | avg saved | deal rate | avg rounds | ms per move | floor-guess error | $ per negotiation |"
    sep = "|---|---|---|---|---|---|---|---|"

    def fmt(name, s):
        fe = f"{s['floor_err']:.1%}" if s["floor_err"] is not None else "n/a"
        return (f"| {name} | {s['n']} | {s['saved']:.1%} | {s['deal']:.0%} | {s['rounds']:.1f} | "
                f"{s['ms']:.1f} | {fe} | ${s['cost']:.4f} |")

    for title, flt in (("All suppliers", lambda r: True),
                       ("Built-in supplier types", lambda r: r["set"] == "built"),
                       ("Held-out supplier types (never seen while building)", lambda r: r["set"] == "held-out")):
        lines += [f"## {title}", "", hdr, sep]
        by = defaultdict(list)
        for r in rows:
            if flt(r):
                by[r["buyer"]].append(r)
        for b in ("split", "llm", "search", "jev"):
            if by[b]:
                lines.append(fmt(b, stats(by[b])))
        lines.append("")

    lines += ["## By supplier type (avg saved / deal rate)", "",
              "| supplier | set | " + " | ".join(sorted({r['buyer'] for r in rows})) + " |",
              "|---|---|" + "---|" * len({r['buyer'] for r in rows})]
    buyers = sorted({r["buyer"] for r in rows})
    for kind in BUILT + HELD_OUT:
        cells = []
        for b in buyers:
            rs = [r for r in rows if r["supplier"] == kind and r["buyer"] == b]
            cells.append(f"{stats(rs)['saved']:.1%} / {stats(rs)['deal']:.0%}" if rs else "-")
        lines.append(f"| {kind} | {'built' if kind in BUILT else 'held-out'} | " + " | ".join(cells) + " |")

    text = "\n".join(lines) + "\n"
    with open(os.path.join(OUT_DIR, "summary.md"), "w") as f:
        f.write(text)
    print("\n" + text)
    print(f"Wrote {os.path.join(OUT_DIR, 'results.csv')} and summary.md")


if __name__ == "__main__":
    main()
