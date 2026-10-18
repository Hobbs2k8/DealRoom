"""Turns structured offers into human-sounding text.

Uses Claude when ANTHROPIC_API_KEY is set; otherwise, or on any error/timeout,
falls back to template strings. Never blocks the negotiation for long.
"""
import logging
import os

log = logging.getLogger("dealroom.writer")

MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-5-5")
TIMEOUT_S = 4.0
_client = None


SYSTEM = ("You write one or two short, plain sentences for a small-business purchasing "
          "negotiation. Never invent numbers; use only the numbers given. No greetings.")


def _asi(prompt: str) -> str | None:
    """Same job via ASI:One (Fetch.ai's LLM) when ASI_ONE_API_KEY is set."""
    from core import asi
    out = asi.chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                   max_tokens=150, timeout=TIMEOUT_S)
    return out["text"] if out and out["text"] else None


def _claude(prompt: str) -> str | None:
    """One short LLM call: Claude if ANTHROPIC_API_KEY is set, else ASI:One if ASI_ONE_API_KEY
    is set. Returns None on any failure so callers use the template."""
    global _client
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _asi(prompt) if os.environ.get("ASI_ONE_API_KEY") else None
    try:
        import anthropic
        if _client is None:
            _client = anthropic.Anthropic(timeout=TIMEOUT_S, max_retries=0)
        resp = _client.beta.messages.create(
            model=MODEL,
            max_tokens=300,
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            system="You write one or two short, plain sentences for a small-business purchasing "
                   "negotiation. Never invent numbers; use only the numbers given. No greetings.",
            messages=[{"role": "user", "content": prompt}],
        )
        if resp.stop_reason == "refusal":
            log.warning("Claude refused; using template")
            return None
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        return text or None
    except Exception as e:  # network, auth, timeout: the demo must keep going
        log.warning("Claude call failed (%s); using template", type(e).__name__)
        return None


def offer_message(price: float, quantity: int, pay_in_days: int, item: str, reason: str,
                  unit: str = "unit", deliver_in_days: int | None = None) -> str:
    """Buyer -> supplier message for an offer."""
    from core.offers import describe_order
    pay = "paid immediately" if pay_in_days == 0 else f"paid in {pay_in_days} days"
    if deliver_in_days is not None:
        pay += f", delivered by day {deliver_in_days}"
    order = describe_order(quantity, item, unit, price)
    template = f"We'd like {order}, {pay}. {reason}"
    text = _claude(f"Write the buyer's offer to the supplier. Offer: {order}, {pay}. "
                   f"Leverage to mention briefly: {reason}")
    return text or template


def owner_message(facts: str) -> str:
    """Buyer -> owner summary. `facts` is already a complete plain-text summary."""
    return _claude(f"Rewrite this update for the business owner, keeping every number: {facts}") or facts
