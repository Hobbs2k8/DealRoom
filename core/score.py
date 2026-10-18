"""Scores a possible deal in dollars, from the owner's point of view."""

CASH_PENALTY = 1_000_000.0   # effectively forbids breaking the owner's cash floor


def cash_ok(total: float, pay_in_days: int, cash: dict) -> bool:
    """Would this payment keep cash at or above the owner's floor once payroll is covered?

    Paying now comes straight out of today's balance. Paying later is assumed to be
    covered by inflows before it falls due, so only payroll is checked.
    """
    projected = cash["cash"] - cash["payroll_next"] - (total if pay_in_days == 0 else 0.0)
    return projected >= cash["cash_floor"]


def deal_value(price: float, quantity: int, pay_in_days: int, list_price: float, cash: dict) -> float:
    """Money saved vs. the current list price, minus a huge penalty if paying now
    would push cash below the owner's floor before the next payroll is covered.

    cash = {"cash": current balance, "payroll_next": payroll due soon,
            "cash_floor": owner's minimum balance}
    """
    saved = (list_price - price) * quantity
    if not cash_ok(price * quantity, pay_in_days, cash):
        saved -= CASH_PENALTY
    return round(saved, 2)
