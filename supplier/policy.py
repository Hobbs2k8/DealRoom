"""Supplier negotiation rules. Plain Python, no Jev, no imports from core/.

The floor is secret: it is never put in any reply. It is only written to
supplier_secret.json for the end-of-demo reveal.
"""
import json
import random
from dataclasses import asdict, dataclass

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
                seed: int | None = None) -> SupplierSecret:
    """Roll a secret supplier. Floor sits 8-18% under list price."""
    rng = random.Random(seed)
    personality = personality or rng.choice(PERSONALITIES)
    return SupplierSecret(
        list_price=list_price,
        floor=round(list_price * rng.uniform(0.82, 0.92), 2),
        personality=personality,
        season=season or rng.choice(("busy", "normal", "slow")),
        max_rounds={"stubborn": 6, "desperate": 8, "bluffer": 6, "walker": 4}[personality],
        likes_prepay=rng.random() < 0.6,
        prepay_discount=round(rng.uniform(0.02, 0.03), 3),
        long_terms_premium=round(rng.uniform(0.01, 0.02), 3),
    )


class SupplierPolicy:
    def __init__(self, secret: SupplierSecret):
        self.s = secret
        self.round = 0
        self.ask = secret.list_price

    def effective_floor(self, pay_in_days: int) -> float:
        """Lowest price the supplier will take for these payment terms."""
        f = self.s.floor
        f *= {"busy": 1.05, "normal": 1.0, "slow": 0.95}[self.s.season]
        if pay_in_days == 0 and self.s.likes_prepay:
            f *= 1 - self.s.prepay_discount
        elif pay_in_days > 30:
            f *= 1 + self.s.long_terms_premium * (pay_in_days - 30) / 15
        return round(f, 2)

    def opening(self, quantity: int) -> dict:
        """First quote: list price at net 30."""
        return self._offer(self.ask, 30, f"Our price for {quantity} units is ${self.ask:,.2f} each, net 30.")

    def respond(self, price: float, quantity: int, pay_in_days: int) -> dict:
        """Answer a buyer offer with accept, a counteroffer, or reject."""
        self.round += 1
        floor = self.effective_floor(pay_in_days)
        p = self.s.personality

        if price < floor * INSULT[p] and (p == "walker" or self.round >= self.s.max_rounds):
            return self._reject("That's far below what we can do. We'll pass.")

        next_ask = round(max(floor, self.ask - CONCEDE[p] * (self.ask - floor)), 2)
        # Bluffer pretends its ask is final in early rounds but keeps it above the floor.
        if p == "bluffer" and self.round <= 2:
            next_ask = round(max(next_ask, floor * 1.04), 2)

        if price >= next_ask or (price >= floor and self.round >= self.s.max_rounds - 1):
            return {"kind": "accept", "price": round(price, 2), "pay_in_days": pay_in_days,
                    "message": f"Deal at ${price:,.2f}, paid in {pay_in_days} days."}
        if self.round >= self.s.max_rounds:
            return self._reject("We've gone as far as we can. No deal this time.")

        self.ask = next_ask
        return self._offer(next_ask, pay_in_days, self._counter_text(next_ask, pay_in_days))

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

    def _offer(self, price: float, pay_in_days: int, message: str) -> dict:
        return {"kind": "offer", "price": round(price, 2), "pay_in_days": pay_in_days, "message": message}

    def _reject(self, reason: str) -> dict:
        return {"kind": "reject", "price": None, "pay_in_days": None, "message": reason}


def write_secret(secret: SupplierSecret, path: str = "supplier_secret.json") -> None:
    """For the end-of-demo reveal only. Never sent to the buyer."""
    with open(path, "w") as f:
        json.dump(asdict(secret), f, indent=2)
