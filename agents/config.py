"""Reads agent settings from .env. Seeds live only in .env, never in code."""
import os
import sys

import certifi
from dotenv import load_dotenv

load_dotenv()
# python.org builds on macOS ship without CA certificates, which makes Agentverse
# registration fail SSL checks and stall startup. certifi's bundle fixes that.
os.environ.setdefault("SSL_CERT_FILE", certifi.where())


def require_seed(name: str) -> str:
    """Exit with a clear message if a seed is missing (addresses depend on it)."""
    value = os.environ.get(name, "").strip()
    if not value:
        sys.exit(f"{name} is not set. Copy .env.example to .env and fill in {name}.")
    return value
