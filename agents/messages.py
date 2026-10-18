"""Messages exchanged between the buyer and supplier agents.

The supplier's floor price never appears in any of these.
"""
from uagents import Model


class NegotiationStart(Model):
    """Buyer opens a negotiation for one item."""
    item: str
    quantity: int
    list_price: float      # current price from the real bills


class Offer(Model):
    """An offer or counteroffer (either side)."""
    price: float
    quantity: int
    pay_in_days: int       # 0 = pay now
    message: str = ""


class Accept(Model):
    """Agreement at these terms. Only a supplier Accept creates a deal."""
    price: float
    pay_in_days: int


class Reject(Model):
    """Walk away; negotiation over."""
    reason: str
