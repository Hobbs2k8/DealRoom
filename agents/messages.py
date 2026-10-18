"""Messages between the buyer and the supplier agents.

Every message carries the request ID, the per-supplier negotiation ID and its own
transaction ID, so each supplier's negotiation is tracked separately. The
supplier's floor price never appears in any of these; neither does the buyer's
ledger, cash balance or cash floor.
"""
from uagents import Model


class NegotiationStart(Model):
    """Buyer -> supplier: request for quote. Only owner-authorized information."""
    request_id: str
    negotiation_id: str
    tx_id: str
    item: str
    quantity: int
    unit: str = "unit"          # "unit" (per item) or "payment" (per recurring bill)
    need_by_days: int = 7
    reference_price: float      # what the buyer pays today (disclosed by the owner's choice)
    vendor_name: str = ""       # how the buyer knows this supplier


class Offer(Model):
    """An offer or counteroffer (either side)."""
    request_id: str = ""
    negotiation_id: str = ""
    tx_id: str = ""
    price: float
    quantity: int
    pay_in_days: int            # 0 = pay now
    deliver_in_days: int | None = None
    reliability: float | None = None   # supplier's public reliability score, if it shares one
    message: str = ""


class Accept(Model):
    """Supplier accepts these exact terms. Only a supplier Accept creates a deal."""
    request_id: str = ""
    negotiation_id: str = ""
    tx_id: str = ""
    price: float
    quantity: int = 0
    pay_in_days: int
    deliver_in_days: int | None = None


class Reject(Model):
    """Either side ends this negotiation, with a reason."""
    request_id: str = ""
    negotiation_id: str = ""
    tx_id: str = ""
    reason: str


class Confirm(Model):
    """Buyer -> supplier: the owner approved; terms are locked."""
    request_id: str
    negotiation_id: str
    tx_id: str


class Cancel(Model):
    """Buyer -> supplier: the request is closed without this supplier."""
    request_id: str
    negotiation_id: str
    tx_id: str
    reason: str


class Withdraw(Model):
    """Supplier -> buyer: backs out of an accepted deal before confirmation."""
    request_id: str
    negotiation_id: str
    tx_id: str
    reason: str
