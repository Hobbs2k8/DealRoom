"""ASI:One (Fetch.ai's LLM) through its OpenAI-compatible API.

Set ASI_ONE_API_KEY in .env. Every call has a short timeout and returns None on any
failure, so callers always have a non-LLM fallback and the demo never stalls.
"""
import logging
import os

import httpx

log = logging.getLogger("dealroom.asi")

BASE_URL = os.environ.get("ASI_ONE_BASE_URL", "https://api.asi1.ai/v1")
MODEL = os.environ.get("ASI_ONE_MODEL", "asi1")


def available() -> bool:
    return bool(os.environ.get("ASI_ONE_API_KEY"))


def chat(messages: list[dict], max_tokens: int = 200, temperature: float = 0.2,
         timeout: float = 8.0) -> dict | None:
    """One chat completion. Returns {"text", "tokens_in", "tokens_out"} or None on failure."""
    key = os.environ.get("ASI_ONE_API_KEY")
    if not key:
        return None
    try:
        r = httpx.post(f"{BASE_URL}/chat/completions", timeout=timeout,
                       headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                       json={"model": MODEL, "messages": messages, "max_tokens": max_tokens,
                             "temperature": temperature})
        r.raise_for_status()
        data = r.json()
        text = (data["choices"][0]["message"].get("content") or "").strip()
        usage = data.get("usage") or {}
        return {"text": text, "tokens_in": usage.get("prompt_tokens", 0),
                "tokens_out": usage.get("completion_tokens", 0)}
    except Exception as e:   # network, auth, rate limit, bad JSON: caller falls back
        log.warning("ASI:One call failed (%s: %s)", type(e).__name__, e)
        return None
