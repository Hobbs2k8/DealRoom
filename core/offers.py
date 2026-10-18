"""The thing being negotiated: unit price and when the buyer pays."""
from dataclasses import dataclass, asdict

PAY_NOW = 0
PAY_LATER = 45


@dataclass(frozen=True)
class Offer:
    price: float        # per unit, dollars
    quantity: int
    pay_in_days: int    # 0 = pay now (prepay), 45 = net 45

    def total(self) -> float:
        return round(self.price * self.quantity, 2)

    def to_dict(self) -> dict:
        return asdict(self)
