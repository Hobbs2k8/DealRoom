"""Scout: per-vendor stats from accounts payable, and the best negotiation opportunity.

Findings from company-001 that shape this file:
- Every vendor is paid 1-3 days after the due date, so a strict on-time rate is 0%
  for everyone. We count a payment as "reliable" if it lands within GRACE_DAYS.
- Price creep only exists on product bills (item_lines). Overhead bills have none.
- Payroll runs are small and frequent, so "near payroll" means a run within 7 days.

Findings from all 100 companies:
- Only 22 have an item bought 6+ times. Many wholesalers buy each item 3-5 times,
  so we fall back to items with MIN_PURCHASES when nothing has STRONG_PURCHASES.
- 66 companies buy no products at all; their bills are account-line overhead. For
  negotiable vendor roles (subcontractors, operating services, rent, insurance) we
  negotiate the recurring bill itself: price = a typical bill, quantity = bills
  expected in the next quarter. Taxes, utilities and lenders are not negotiable.
"""
import statistics
from collections import defaultdict
from dataclasses import dataclass, field

from core.data import company_name, load

GRACE_DAYS = 3          # paid within this many days of due counts as reliable
PAYROLL_WINDOW = 7      # open bill due within this many days of a payroll run
STRONG_PURCHASES = 6    # preferred minimum history for an item's price trend
MIN_PURCHASES = 3       # fallback minimum when no item has a strong history
MIN_RECURRING_BILLS = 4 # minimum bills for a recurring overhead negotiation
NEXT_QUARTER_DAYS = 90
# Bill amounts that swing more than this (std/mean) reflect volume, not price, so a
# rise in them is not counted as price creep (e.g. a courier billed per shipment).
STEADY_BILL_CV = 0.15
# Vendor supply_role -> what we call the recurring bill. Roles not listed
# (government, utility, lender) are not negotiable.
SERVICE_LABELS = {
    "subcontract": "subcontracted work",
    "operating": "service",
    "premises": "rent",
    "insurance": "insurance premium",
    "product": "supply order",
}


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
    typical_qty: int = 0         # median units per bill (product) or bills next quarter (service)
    kind: str = "product"        # "product" = per-unit price; "service" = per-bill price
    unit: str = "unit"           # what one quantity is: "unit" or "payment"


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


def _window(n: int) -> int:
    """How many early/late points to average when measuring a trend."""
    return max(1, min(5, n // 2))


def _item_price_trend(bills: list) -> tuple:
    """Pick the item with the largest price rise over the year.

    Items with STRONG_PURCHASES+ purchases win; items with MIN_PURCHASES are a fallback.
    Returns (item_name, start_price, latest_price, change_fraction, median_qty).
    """
    series = defaultdict(list)
    for b in bills:
        for line in b["item_lines"]:
            series[line["item_name"]].append(
                (b["txn_sim_day"], float(line["unit_price_amount"]), int(line["quantity"]))
            )
    for min_n in (STRONG_PURCHASES, MIN_PURCHASES):
        best = (None, None, None, 0.0, 0)
        for item, pts in series.items():
            if len(pts) < min_n:
                continue
            pts.sort()
            w = _window(len(pts))
            start = statistics.mean(p for _, p, _ in pts[:w])
            now = statistics.mean(p for _, p, _ in pts[-w:])
            change = now / start - 1
            if best[0] is None or change > best[3]:
                qty = int(statistics.median(q for _, _, q in pts))
                best = (item, round(start, 2), round(now, 2), change, qty)
        if best[0]:
            return best
    return (None, None, None, 0.0, 0)


def _service_trend(bills: list, role: str | None, today: int) -> tuple:
    """For a negotiable overhead vendor, treat each recurring bill as the 'unit'.

    Returns (label, start_amount, recent_amount, change_fraction, bills_next_quarter),
    or all-None when the vendor isn't negotiable or doesn't bill regularly.
    """
    if role not in SERVICE_LABELS or len(bills) < MIN_RECURRING_BILLS:
        return (None, None, None, 0.0, 0)
    pts = sorted((b["txn_sim_day"], float(b["total_amount"])) for b in bills)
    w = _window(len(pts))
    start = statistics.median(a for _, a in pts[:w])
    now = statistics.median(a for _, a in pts[-w:])
    if start <= 0 or now <= 0:
        return (None, None, None, 0.0, 0)
    amounts = [a for _, a in pts]
    steady = statistics.pstdev(amounts) / statistics.mean(amounts) <= STEADY_BILL_CV
    change = now / start - 1 if steady else 0.0   # variable bills: growth is volume, not price
    recent = sum(1 for d, _ in pts if d > today - NEXT_QUARTER_DAYS)
    return (SERVICE_LABELS[role], round(start, 2), round(now, 2), change, max(1, recent))


def vendor_stats(company_id: str) -> list[VendorStats]:
    """Compute stats for every vendor that has bills."""
    bills = load(company_id, "bills")
    vendors = load(company_id, "vendors")
    names = {v["id"]: v["display_name"] for v in vendors}
    roles = {v["id"]: v.get("supply_role") for v in vendors}
    today = max((b["txn_sim_day"] for b in bills), default=0)
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
        kind, unit = "product", "unit"
        if not item and not any(b["item_lines"] for b in vbills):
            item, p0, p1, change, qty = _service_trend(vbills, roles.get(vid), today)
            kind, unit = "service", "payment"
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
            price_change=change, typical_qty=qty, kind=kind, unit=unit,
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
        what = v.top_item if v.kind == "product" else f"A typical {v.top_item} bill"
        reasons.append(f"{what} went from ${v.price_start:,.2f} to ${v.price_now:,.2f} "
                       f"(+{v.price_change:.1%}) over the year")
    elif v.kind == "service":
        reasons.append(f"You pay about ${v.price_now:,.2f} per {v.top_item} bill, "
                       f"{v.typical_qty} bills expected next quarter")
    score += min(v.total_spend / 50_000, 10)
    reasons.append(f"${v.total_spend:,.0f} spent across {v.bills} bills: you're a big customer")
    if v.on_time_rate >= 0.9:
        score += 5
        reasons.append(f"{v.on_time_rate:.0%} of bills paid within {GRACE_DAYS} days of due "
                       f"(avg {v.avg_days_late} days late): a reliable payer")
    if v.open_near_payroll:
        score += 3
        total = sum(b["amount"] for b in v.open_near_payroll)
        n = len(v.open_near_payroll)
        reasons.append(f"{n} open bill{'s' if n != 1 else ''} (${total:,.0f}) due within "
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
