"""Supplier negotiation rules. Plain Python, no Jev, no imports from core/.

The floor is secret: it is never put in any reply. It is only written to
supplier_secret.json for the end-of-demo reveal.

With a SupplierProfile the policy also enforces the business's capacity, delivery
lead time and payment terms, and can withdraw an accepted-but-unconfirmed deal
when the judge cuts its capacity. Without one it behaves as before (unlimited
capacity, delivers any day, any payment terms).
"""
import json
import random
from dataclasses import asdict, dataclass

from supplier import controls
from supplier.profiles import SupplierProfile

PERSONALITIES = ("stubborn", "desperate", "bluffer", "walker")

# How much of the gap to its floor the supplier gives up each round.
CONCEDE = {"stubborn": 0.18, "desperate": 0.55, "bluffer": 0.30, "walker": 0.30}
# Offers below floor * this are insulting; a walker walks away.
INSULT = {"stubborn": 0.80, "desperate": 0.70, "bluffer": 0.80, "walker": 0.90}


@dataclass
class SupplierSecret:
    list_price: float
    floor: float           # at standard terms, before season and payment adjustments
    personality: str
    season: str            # "busy" | "normal" | "slow"
    max_rounds: int
    likes_prepay: bool
    prepay_discount: float  # 0.02-0.03 when likes_prepay
    long_terms_premium: float


def make_secret(list_price: float, personality: str | None = None, season: str | None = None,
                seed: int | None = None, floor_range: tuple = (0.82, 0.92),
                likes_prepay: bool | None = None) -> SupplierSecret:
    """Roll a secret supplier. Floor sits 8-18% under list price by default."""
    rng = random.Random(seed)
    personality = personality or rng.choice(PERSONALITIES)
    prepay_roll = rng.random() < 0.6
    return SupplierSecret(
        list_price=list_price,
        floor=round(list_price * rng.uniform(*floor_range), 2),
        personality=personality,
        season=season or rng.choice(("busy", "normal", "slow")),
        max_rounds={"stubborn": 6, "desperate": 8, "bluffer": 6, "walker": 4}[personality],
        likes_prepay=prepay_roll if likes_prepay is None else likes_prepay,
        prepay_discount=round(rng.uniform(0.02, 0.03), 3),
        long_terms_premium=round(rng.uniform(0.01, 0.02), 3),
    )


def secret_for_profile(profile: SupplierProfile, reference_price: float, seed: int | None = None) -> SupplierSecret:
    """Secret floor and settings for one simulated business, priced off the buyer's reference."""
    return make_secret(round(reference_price * profile.list_multiplier, 2), profile.personality,
                       profile.season, seed=seed, floor_range=profile.floor_range,
                       likes_prepay=profile.likes_prepay)


class SupplierPolicy:
    def __init__(self, secret: SupplierSecret, profile: SupplierProfile | None = None):
        self.s = secret
        self.profile = profile
        self.round = 0
        self.ask = secret.list_price
        self.confirmed = False
        self.accepted: dict | None = None   # terms this supplier accepted, pending buyer confirmation

    # ---- business constraints -------------------------------------------
    def capacity(self) -> int | None:
        """Units it can commit now (judge overrides apply). None = unlimited."""
        if not self.profile:
            return None
        override = controls.capacity_override(self.profile.id)
        return self.profile.capacity if override is None else override

    def lead_days(self) -> int:
        return self.profile.lead_days if self.profile else 0

    def check_withdraw(self) -> str | None:
        """If capacity no longer covers an accepted, unconfirmed deal, say why we withdraw."""
        if self.confirmed or not self.accepted:
            return None
        cap = self.capacity()
        if cap is not None and cap < self.accepted["quantity"]:
            self.accepted = None
            return f"We've lost capacity and can now supply only {cap}. We have to withdraw our acceptance."
        return None

    def effective_floor(self, pay_in_days: int) -> float:
        """Lowest price the supplier will take for these payment terms."""
        f = self.s.floor
        f *= {"busy": 1.05, "normal": 1.0, "slow": 0.95}[self.s.season]
        if pay_in_days == 0 and self.s.likes_prepay:
            f *= 1 - self.s.prepay_discount
        elif pay_in_days > 30:
            f *= 1 + self.s.long_terms_premium * (pay_in_days - 30) / 15
        return round(f, 2)

    def opening(self, quantity: int, unit: str = "unit") -> dict:
        """First quote: list price, its usual payment terms, its delivery lead time."""
        if self.profile and self.profile.product_only and unit == "payment":
            return self._reject("We only sell products; we don't provide this kind of service.")
        pay = self.profile.pay_terms if self.profile else 30
        cap = self.capacity()
        qty = quantity if cap is None else min(quantity, cap)
        terms = "payment upfront" if pay == 0 else f"net {pay}"
        msg = f"Our price for {qty} is ${self.ask:,.2f} each, {terms}"
        if self.profile:
            msg += f", delivered in {self.lead_days()} days"
        if qty < quantity:
            msg += f". We can only commit {qty} of the {quantity} you asked for"
        return self._offer(self.ask, pay, msg + ".", qty)

    def respond(self, price: float, quantity: int, pay_in_days: int,
                deliver_in_days: int | None = None) -> dict:
        """Answer a buyer offer with accept, a counteroffer, or reject."""
        if self.confirmed:
            return self._reject("This order is already confirmed; terms can't change.")
        self.round += 1
        cap = self.capacity()
        if cap is not None and cap <= 0:
            return self._reject("We're out of stock and can't take this order.")
        if cap is not None and cap < quantity:
            return self._offer(self.ask, pay_in_days, f"We can only supply {cap}, not {quantity}.", cap)
        if deliver_in_days is not None and deliver_in_days < self.lead_days():
            return self._offer(self.ask, pay_in_days,
                               f"The earliest we can deliver is day {self.lead_days()}.", quantity)
        if self.profile and self.profile.prepay_only and pay_in_days > 0:
            return self._offer(self.ask, 0, f"We only work with payment upfront. ${self.ask:,.2f}, paid now.",
                               quantity)
        if self.profile and pay_in_days > self.profile.max_pay_days:
            return self._offer(self.ask, self.profile.max_pay_days,
                               f"Our longest terms are net {self.profile.max_pay_days}.", quantity)
        floor = self.effective_floor(pay_in_days)
        p = self.s.personality

        if price < floor * INSULT[p] and (p == "walker" or self.round >= self.s.max_rounds):
            return self._reject("That's far below what we can do. We'll pass.")

        next_ask = round(max(floor, self.ask - CONCEDE[p] * (self.ask - floor)), 2)
        # Bluffer pretends its ask is final in early rounds but keeps it above the floor.
        if p == "bluffer" and self.round <= 2:
            next_ask = round(max(next_ask, floor * 1.04), 2)

        if price >= next_ask or (price >= floor and self.round >= self.s.max_rounds - 1):
            deliver = max(deliver_in_days or 0, self.lead_days()) if self.profile else deliver_in_days
            self.accepted = {"price": round(price, 2), "quantity": quantity, "pay_in_days": pay_in_days,
                             "deliver_in_days": deliver}
            return {"kind": "accept", **self.accepted,
                    "message": f"Deal at ${price:,.2f}, paid in {pay_in_days} days."}
        if self.round >= self.s.max_rounds:
            return self._reject("We've gone as far as we can. No deal this time.")

        self.ask = next_ask
        return self._offer(next_ask, pay_in_days, self._counter_text(next_ask, pay_in_days), quantity)

    def confirm(self) -> None:
        """Buyer confirmed after owner approval: terms are now locked."""
        self.confirmed = True

    # ---- message helpers ------------------------------------------------
    def _counter_text(self, ask: float, pay_in_days: int) -> str:
        p = self.s.personality
        if p == "bluffer" and self.round <= 2:
            return f"${ask:,.2f} is our final offer."
        if p == "stubborn":
            return f"Costs are up for us too. Best I can do is ${ask:,.2f}."
        if p == "desperate":
            return f"We'd like to keep your business. How about ${ask:,.2f}?"
        if p == "walker":
            return f"${ask:,.2f}. We don't have much room left."
        return f"We can do ${ask:,.2f}, paid in {pay_in_days} days."

    def _offer(self, price: float, pay_in_days: int, message: str, quantity: int | None = None) -> dict:
        out = {"kind": "offer", "price": round(price, 2), "pay_in_days": pay_in_days, "message": message}
        if quantity is not None:
            out["quantity"] = quantity
        if self.profile:
            out["deliver_in_days"] = self.lead_days()
            out["reliability"] = self.profile.reliability
        return out

    def _reject(self, reason: str) -> dict:
        return {"kind": "reject", "price": None, "pay_in_days": None, "message": reason}


def write_secret(secret: SupplierSecret, path: str = "supplier_secret.json") -> None:
    """For the end-of-demo reveal only. Never sent to the buyer."""
    with open(path, "w") as f:
        json.dump(asdict(secret), f, indent=2)
