"""Loads one company's QuickBooks YAML files from data/.

Never reads anything under a hidden/ folder: that is simulation ground truth.
"""
import glob
import os
from functools import lru_cache

import yaml

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")


def company_dir(company_id: str) -> str:
    """Return the world folder for a company, e.g. data/company-001/rwm-v4/world-xxxx."""
    matches = glob.glob(os.path.join(DATA_DIR, company_id, "rwm-v4", "world-*"))
    if not matches:
        raise FileNotFoundError(f"No data for {company_id} under {DATA_DIR}")
    return matches[0]


@lru_cache(maxsize=64)
def load(company_id: str, name: str) -> list | dict:
    """Load one entity file (e.g. 'bills' or 'reports/ap_aging'). Empty files return []."""
    if "hidden" in name.split("/"):
        raise PermissionError("Agents may not read hidden/ simulation files")
    path = os.path.join(company_dir(company_id), f"{name}.yaml")
    with open(path) as f:
        return yaml.safe_load(f) or []


def company_name(company_id: str) -> str:
    """Trade name of the company, e.g. 'Hearthloaf Bakeries'."""
    profile = load(company_id, "company")
    return profile[0]["trade_name"] if isinstance(profile, list) else profile["trade_name"]
