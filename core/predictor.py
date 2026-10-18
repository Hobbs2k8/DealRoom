"""Predicts how a supplier will answer a candidate offer.

SupplierPredictor.predict(state, candidates) returns one dict per candidate:
{"accept": p, "counter": p, "walk": p}. Implementations:
- HeuristicPredictor: statistics only, needs no API key (this file).
- JevPredictor: TypeSafe Jev (System One), see core/jev.py.

make_predictor() picks Jev when TYPESAFE_API_KEY is set, else the heuristic.
"""
import logging
import math
import os
from dataclasses import dataclass, field

from core.belief import terms_factor
from core.offers import Offer


@dataclass
class PredictState:
    floor_std: float      # one sampled floor at standard terms
    ask: float            # supplier's current asking price
    list_price: float
    round: int
    max_rounds: int       # buyer's guess of supplier patience
    depth: int = 0        # 0 = the real next move; >0 = inside a simulated playout
    context: dict = field(default_factory=dict)   # negotiation history, for Jev


class SupplierPredictor:
    def predict(self, state: PredictState, candidates: list[Offer]) -> list[dict]:
        raise NotImplementedError


class HeuristicPredictor(SupplierPredictor):
    """Logistic acceptance around the (terms-adjusted) floor, walk risk for lowballs."""

    def predict(self, state: PredictState, candidates: list[Offer]) -> list[dict]:
        return [self._one(state, c) for c in candidates]

    def _one(self, s: PredictState, offer: Offer) -> dict:
        floor = s.floor_std * terms_factor(offer.pay_in_days)
        scale = s.list_price * 0.015
        if offer.price >= s.ask:
            accept = 0.97
        else:
            # Above the floor, acceptance rises as we close the gap to the ask and as rounds run out.
            urgency = s.round / max(1, s.max_rounds)
            z = (offer.price - floor) / scale - 1.5 + 2.5 * urgency
            accept = 1 / (1 + math.exp(-z)) if offer.price >= floor else 0.02
        insult = max(0.0, (floor - offer.price) / floor)          # how far under the floor
        walk = min(0.9, insult * 3 + (0.15 if s.round >= s.max_rounds else 0.0))
        walk = min(walk, 1 - accept)
        return {"accept": accept, "counter": max(0.0, 1 - accept - walk), "walk": walk}


def make_predictor(kind: str = "auto") -> SupplierPredictor:
    """'auto' uses Jev when TYPESAFE_API_KEY is set; 'heuristic' or 'jev' force one."""
    if kind == "heuristic" or (kind == "auto" and not os.environ.get("TYPESAFE_API_KEY")):
        return HeuristicPredictor()
    try:
        from core.jev import JevPredictor
        return JevPredictor()
    except Exception as e:   # missing package or bad config: never block the demo
        logging.getLogger("dealroom.predictor").warning("Jev unavailable (%s); using heuristic", e)
        return HeuristicPredictor()
