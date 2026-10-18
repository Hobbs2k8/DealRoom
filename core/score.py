"""Scores a possible deal in dollars, from the owner's point of view."""

CASH_PENALTY = 1_000_000.0   # effectively forbids breaking the owner's cash floor


def deal_value(price: float, quantity: int, pay_in_days: int, list_price: float, cash: dict) -> float:
    """Money saved vs. the current list price, minus a huge penalty if paying now
    would push cash below the owner's floor before the next payroll is covered.

    cash = {"cash": current balance, "payroll_next": payroll due soon,
            "cash_floor": owner's minimum balance}
    """
    saved = (list_price - price) * quantity
    if pay_in_days == 0:
        projected = cash["cash"] - price * quantity - cash["payroll_next"]
        if projected < cash["cash_floor"]:
            saved -= CASH_PENALTY
    return round(saved, 2)
