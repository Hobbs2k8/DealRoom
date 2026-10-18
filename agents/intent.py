"""Reads what the owner means, using ASI:One. Falls back to None (caller uses keywords).

Only used for messages the keyword rules didn't catch, so exact commands stay instant.
"""
import json
import re

from core import asi

ACTIONS = ("start", "approve", "decline", "status", "compare", "explain", "help",
           "passive", "balanced", "aggressive", "floor", "chat")

SYSTEM = (
    "You route messages from a small-business owner to a purchasing agent that finds supplier "
    "bills worth renegotiating and negotiates them. Pick exactly one action:\n"
    "start = find savings / negotiate / any request to cut costs or get a better deal\n"
    "approve = owner accepts the recommended deal (yes, sounds good, do it)\n"
    "decline = owner rejects the deal (no, cancel, not now)\n"
    "status = asks how it's going\n"
    "compare = wants to see all offers side by side\n"
    "explain = asks why, how, or for the reasoning behind a deal\n"
    "help = asks what the agent can do\n"
    "passive / balanced / aggressive = wants a different negotiation style\n"
    "floor = sets a minimum cash balance (put the dollar amount in \"amount\")\n"
    "chat = small talk unrelated to purchasing\n"
    "If the owner names a supplier to buy from, put it in \"supplier\".\n"
    'Reply with ONLY JSON: {"action": "...", "amount": null, "supplier": null}'
)


def classify(text: str, waiting_for_approval: bool) -> dict | None:
    """Return {"action", "amount", "supplier"} or None if ASI:One is unavailable or unclear."""
    if not asi.available():
        return None
    context = ("A deal is waiting for the owner's approval right now. "
               if waiting_for_approval else "No deal is waiting for approval right now. ")
    out = asi.chat([{"role": "system", "content": SYSTEM},
                    {"role": "user", "content": context + "Owner message: " + text}],
                   max_tokens=80, temperature=0.0, timeout=6.0)
    if not out:
        return None
    m = re.search(r"\{.*\}", out["text"], re.S)
    try:
        d = json.loads(m.group(0))
    except Exception:
        return None
    action = str(d.get("action", "")).lower().strip()
    if action not in ACTIONS:
        return None
    amount = d.get("amount")
    try:
        amount = float(str(amount).replace("$", "").replace(",", "")) if amount is not None else None
    except ValueError:
        amount = None
    supplier = d.get("supplier") or ""
    return {"action": action, "amount": amount, "supplier": str(supplier)}
