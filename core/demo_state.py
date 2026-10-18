"""Writes demo_state.json after every round for the separate demo screen."""
import json
import os
import tempfile

PATH = os.environ.get("DEMO_STATE_PATH", "demo_state.json")


def write(state: dict, path: str = PATH) -> None:
    """Atomic write so the demo screen never reads a half-written file."""
    folder = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=folder, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, path)
