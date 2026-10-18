"""Judge-only simulation controls (e.g. a supplier losing capacity mid-demo).

The supplier agents read this file to learn about events in their own world.
The buyer never reads it; it only sees the consequences in supplier messages.
"""
import json
import os

PATH = os.environ.get("MARKET_CONTROLS", "market_controls.json")


def read(path: str = PATH) -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def capacity_override(supplier_id: str, path: str = PATH) -> int | None:
    """Capacity set by the judge for this supplier, or None if untouched."""
    value = read(path).get("capacity", {}).get(supplier_id)
    return None if value is None else int(value)


def set_capacity(supplier_id: str, capacity: int | None, path: str = PATH) -> dict:
    """Judge action: change (or with None, restore) a supplier's capacity."""
    data = read(path)
    caps = data.setdefault("capacity", {})
    if capacity is None:
        caps.pop(supplier_id, None)
    else:
        caps[supplier_id] = int(capacity)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return data


def reset(path: str = PATH) -> None:
    if os.path.exists(path):
        os.remove(path)
