"""The thing being negotiated: unit price and when the buyer pays."""
from dataclasses import dataclass, asdict

PAY_NOW = 0
PAY_LATER = 45


@dataclass(frozen=True)
class Offer:
    price: float        # per unit, dollars
    quantity: int
    pay_in_days: int    # 0 = pay now (prepay), 45 = net 45
    deliver_in_days: int | None = None   # requested delivery day; None = supplier's choice

    def total(self) -> float:
        return round(self.price * self.quantity, 2)

    def to_dict(self) -> dict:
        return asdict(self)


def describe_order(quantity: int, item: str, unit: str, price: float) -> str:
    """Human wording for an order: per-unit products or per-payment services.

    describe_order(255, "Croissant Tray", "unit", 9.86) -> "255 x Croissant Tray at $9.86 each"
    describe_order(3, "rent", "payment", 1500)          -> "3 rent payments of $1,500.00"
    """
    if unit == "payment":
        plural = "s" if quantity != 1 else ""
        return f"{quantity} {item} payment{plural} of ${price:,.2f}"
    return f"{quantity:,} x {item} at ${price:,.2f} each"
