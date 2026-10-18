"""Simulated supplier businesses for the marketplace. Supplier-side, private.

Each profile is one independent business: its own prices, capacity, delivery
lead time, payment terms, negotiation personality and reliability record.
The buyer only ever sees what a supplier chooses to share in its messages
(offers, delivery day, public reliability score), never the rest of this file.

"incumbent" is whichever vendor the buyer already uses (its name comes from the
buyer's request); the other two are simulated competitors. All are simulated.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class SupplierProfile:
    id: str
    name: str                    # "" = use the vendor name in the buyer's request (incumbent)
    list_multiplier: float       # list price relative to what the buyer pays today
    capacity: int                # units (or payments) it can commit this cycle
    lead_days: int               # earliest delivery, days from order
    pay_terms: int               # payment days in its opening quote
    prepay_only: bool            # refuses anything but payment upfront
    max_pay_days: int            # longest payment term it will accept
    reliability: float           # public on-time fulfillment score, 0-1 (shared with buyers)
    personality: str             # stubborn | desperate | bluffer | walker
    season: str                  # busy | normal | slow
    floor_range: tuple = (0.84, 0.92)   # secret floor as a fraction of its list price
    likes_prepay: bool = True
    history_note: str = ""       # public track record line
    product_only: bool = True    # declines requests for recurring services (rent, contracts)


PROFILES: dict[str, SupplierProfile] = {
    "incumbent": SupplierProfile(
        id="incumbent", name="", list_multiplier=1.00, capacity=2000, lead_days=4,
        pay_terms=30, prepay_only=False, max_pay_days=45, reliability=0.97,
        personality="stubborn", season="normal", floor_range=(0.88, 0.93),
        history_note="Your current supplier; 133 orders delivered this year.",
        product_only=False,
    ),
    "harborline": SupplierProfile(
        id="harborline", name="Harborline Wholesale (simulated)", list_multiplier=0.92,
        capacity=1500, lead_days=9, pay_terms=0, prepay_only=True, max_pay_days=0,
        reliability=0.86, personality="walker", season="slow", floor_range=(0.86, 0.91),
        history_note="Lowest list prices; ships from a regional warehouse.",
    ),
    "prairie": SupplierProfile(
        id="prairie", name="Prairie Oven Supply (simulated)", list_multiplier=0.97,
        capacity=600, lead_days=3, pay_terms=45, prepay_only=False, max_pay_days=45,
        reliability=0.94, personality="desperate", season="normal", floor_range=(0.85, 0.90),
        history_note="Newer supplier looking to win accounts; local delivery.",
    ),
}
