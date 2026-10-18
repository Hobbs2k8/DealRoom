"""Scout: per-vendor stats from accounts payable, and the best negotiation opportunity.

Findings from company-001 that shape this file:
- Every vendor is paid 1-3 days after the due date, so a strict on-time rate is 0%
  for everyone. We count a payment as "reliable" if it lands within GRACE_DAYS.
- Price creep only exists on product bills (item_lines). Overhead bills have none.
- Payroll runs are small and frequent, so "near payroll" means a run within 7 days.
"""
import statistics
from collections import defaultdict
from dataclasses import dataclass, field

from core.data import company_name, load

GRACE_DAYS = 3          # paid within this many days of due counts as reliable
PAYROLL_WINDOW = 7      # open bill due within this many days of a payroll run


@dataclass
class VendorStats:
    vendor_id: str
    name: str
    bills: int
    total_spend: float
    on_time_rate: float          # paid within GRACE_DAYS of due
    strict_on_time_rate: float   # paid on or before due
    avg_days_late: float
    open_bills: list = field(default_factory=list)   # [{id, due_day, amount}]
    open_near_payroll: list = field(default_factory=list)
    top_item: str | None = None
    price_start: float | None = None
    price_now: float | None = None
    price_change: float = 0.0    # fraction, e.g. 0.127 = +12.7%
    typical_qty: int = 0         # median units per bill for top_item


@dataclass
class Opportunity:
    company: str
    vendor: VendorStats
    score: float
    reasons: list
    today: int                   # sim day of the latest data


def _paid_days(company_id: str) -> dict:
    """Map bill id -> sim day it was paid."""
    out = {}
    for pay in load(company_id, "bill_payments"):
        for app in pay["applications"]:
            out[app["document_id"]] = pay["txn_sim_day"]
    return out


def _payroll_days(company_id: str) -> list:
    return sorted({run["sim_day"] for run in load(company_id, "payroll_runs")})


def _item_price_trend(bills: list) -> tuple:
    """Pick the item with the largest year-over-year price rise (min 6 purchases).

    Returns (item_name, start_price, latest_price, change_fraction, median_qty).
    """
    series = defaultdict(list)
    for b in bills:
        for line in b["item_lines"]:
            series[line["item_name"]].append(
                (b["txn_sim_day"], float(line["unit_price_amount"]), int(line["quantity"]))
            )
    best = (None, None, None, 0.0, 0)
    for item, pts in series.items():
        if len(pts) < 6:
            continue
        pts.sort()
        start = statistics.mean(p for _, p, _ in pts[:5])
        now = statistics.mean(p for _, p, _ in pts[-5:])
        change = now / start - 1
        if best[0] is None or change > best[3]:
            qty = int(statistics.median(q for _, _, q in pts))
            best = (item, round(start, 2), round(now, 2), change, qty)
    return best


def vendor_stats(company_id: str) -> list[VendorStats]:
    """Compute stats for every vendor that has bills."""
    bills = load(company_id, "bills")
    names = {v["id"]: v["display_name"] for v in load(company_id, "vendors")}
    paid = _paid_days(company_id)
    payroll = _payroll_days(company_id)
    by_vendor = defaultdict(list)
    for b in bills:
        by_vendor[b["vendor_id"]].append(b)

    out = []
    for vid, vbills in by_vendor.items():
        late = [paid[b["id"]] - b["due_sim_day"] for b in vbills if b["id"] in paid]
        open_bills = [
            {"id": b["id"], "due_day": b["due_sim_day"], "amount": float(b["total_amount"])}
            for b in vbills if b["id"] not in paid
        ]
        near = [
            ob for ob in open_bills
            if any(abs(ob["due_day"] - d) <= PAYROLL_WINDOW for d in payroll)
        ]
        item, p0, p1, change, qty = _item_price_trend(vbills)
        out.append(VendorStats(
            vendor_id=vid,
            name=names.get(vid, vbills[0]["vendor_name"]),
            bills=len(vbills),
            total_spend=round(sum(float(b["total_amount"]) for b in vbills), 2),
            on_time_rate=sum(d <= GRACE_DAYS for d in late) / max(1, len(late)),
            strict_on_time_rate=sum(d <= 0 for d in late) / max(1, len(late)),
            avg_days_late=round(statistics.mean(late), 1) if late else 0.0,
            open_bills=open_bills,
            open_near_payroll=near,
            top_item=item, price_start=p0, price_now=p1,
            price_change=change, typical_qty=qty,
        ))
    return sorted(out, key=lambda v: -v.total_spend)


def _score(v: VendorStats) -> tuple[float, list]:
    """Rank a vendor as a negotiation target and say why, in plain words."""
    if not v.top_item:
        return 0.0, ["no product purchases to renegotiate"]
    reasons = []
    score = 0.0
    if v.price_change > 0.02:
        score += v.price_change * 100
        reasons.append(f"{v.top_item} went from ${v.price_start:.2f} to ${v.price_now:.2f} "
                       f"(+{v.price_change:.1%}) over the year")
    score += min(v.total_spend / 50_000, 10)
    reasons.append(f"${v.total_spend:,.0f} spent across {v.bills} bills: you're a big customer")
    if v.on_time_rate >= 0.9:
        score += 5
        reasons.append(f"{v.on_time_rate:.0%} of bills paid within {GRACE_DAYS} days of due "
                       f"(avg {v.avg_days_late} days late): a reliable payer")
    if v.open_near_payroll:
        score += 3
        total = sum(b["amount"] for b in v.open_near_payroll)
        reasons.append(f"{len(v.open_near_payroll)} open bills (${total:,.0f}) due within "
                       f"{PAYROLL_WINDOW} days of a payroll run")
    return score, reasons


def best_opportunity(company_id: str) -> Opportunity | None:
    """Pick the single best vendor to negotiate with."""
    ranked = []
    for v in vendor_stats(company_id):
        s, reasons = _score(v)
        if s > 0:
            ranked.append((s, v, reasons))
    if not ranked:
        return None
    s, v, reasons = max(ranked, key=lambda r: r[0])
    today = max(b["sim_day"] for b in load(company_id, "bank_transactions"))
    return Opportunity(company_name(company_id), v, round(s, 1), reasons, today)


def cash_context(company_id: str, horizon: int = 14) -> dict:
    """Current cash and payroll due in the next `horizon` days, for scoring."""
    bank = load(company_id, "bank_transactions")
    last = max(bank, key=lambda t: (t["sim_day"], t["id"]))
    today = last["sim_day"]
    runs = load(company_id, "payroll_runs")
    # Project payroll forward using the average weekly payroll of the last 4 weeks.
    recent = [float(r["total_amount"]) for r in runs if r["sim_day"] > today - 28]
    weekly = sum(recent) / 4 if recent else 0.0
    return {
        "today": today,
        "cash": float(last["running_balance_amount"]),
        "payroll_next": round(weekly * horizon / 7, 2),
        "open_payables": sum(float(r["balance"]) for r in load(company_id, "reports/ap_aging")["rows"]),
    }
