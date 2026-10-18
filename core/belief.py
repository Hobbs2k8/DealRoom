"""Buyer's belief about the supplier's secret floor price.

Kept as weighted samples of the floor *at standard terms* (net 30). Each supplier
reply reweights the samples, so the low/high range shrinks round by round.
The buyer only knows rough industry norms for how terms move the floor; it never
sees the supplier's code or numbers.
"""
import math
import random

N_SAMPLES = 400
# Industry rule of thumb the buyer assumes (not the supplier's real numbers).
ASSUMED_PREPAY_DISCOUNT = 0.025
ASSUMED_LONG_TERMS_PREMIUM = 0.015
# Concession speeds the buyer considers plausible when reading counteroffers.
CONCESSION_RATES = (0.15, 0.3, 0.45, 0.6)


def terms_factor(pay_in_days: int) -> float:
    """How the buyer thinks payment timing shifts the supplier's floor."""
    if pay_in_days == 0:
        return 1 - ASSUMED_PREPAY_DISCOUNT
    if pay_in_days > 30:
        return 1 + ASSUMED_LONG_TERMS_PREMIUM
    return 1.0


class FloorBelief:
    def __init__(self, list_price: float, low_frac: float = 0.70, seed: int | None = None):
        rng = random.Random(seed)
        self.list_price = list_price
        self.samples = [rng.uniform(list_price * low_frac, list_price) for _ in range(N_SAMPLES)]
        self.weights = [1.0] * N_SAMPLES
        self._rng = rng

    # ---- updates -------------------------------------------------------
    def _reweight(self, fn) -> None:
        self.weights = [w * fn(f) for f, w in zip(self.samples, self.weights)]
        total = sum(self.weights)
        if total <= 1e-12:      # evidence contradicted everything: reset softly
            self.weights = [1.0] * N_SAMPLES
        self._maybe_resample()

    def _maybe_resample(self) -> None:
        """Resample with jitter when weights get too concentrated, to keep the range smooth."""
        total = sum(self.weights)
        ess = total ** 2 / sum(w * w for w in self.weights)
        if ess > N_SAMPLES / 3:
            return
        jitter = self.list_price * 0.005
        picks = self._rng.choices(self.samples, weights=self.weights, k=N_SAMPLES)
        self.samples = [p + self._rng.gauss(0, jitter) for p in picks]
        self.weights = [1.0] * N_SAMPLES

    def observe_counter(self, buyer_price: float, ask: float, prev_ask: float | None, pay_in_days: int) -> None:
        """Supplier countered `ask` after the buyer offered `buyer_price`."""
        tf = terms_factor(pay_in_days)
        ask_std, offer_std = ask / tf, buyer_price / tf
        prev_std = prev_ask / tf if prev_ask else None
        width = self.list_price * 0.03

        def likelihood(f: float) -> float:
            if f > ask_std * 1.005:          # suppliers don't ask below their floor
                return 0.0
            like = 0.6 if f < offer_std else 1.0    # they turned down a price above floor: somewhat less likely
            if prev_std and prev_std > ask_std:     # concession size hints at the distance to floor
                drop = prev_std - ask_std
                est = [ask_std - drop * (1 - c) / c for c in CONCESSION_RATES]
                like *= 0.15 + sum(math.exp(-((f - e) / width) ** 2 / 2) for e in est) / len(est)
            return like

        self._reweight(likelihood)

    def observe_reject(self, buyer_price: float, pay_in_days: int) -> None:
        """Supplier walked away: the offer was probably well under the floor."""
        offer_std = buyer_price / terms_factor(pay_in_days)
        self._reweight(lambda f: 1.0 if f > offer_std else 0.2)

    def observe_accept(self, price: float, pay_in_days: int) -> None:
        """Supplier accepted: the floor is at or below this price."""
        p_std = price / terms_factor(pay_in_days)
        self._reweight(lambda f: 1.0 if f <= p_std * 1.005 else 0.0)

    # ---- queries -------------------------------------------------------
    def _quantile(self, q: float) -> float:
        pairs = sorted(zip(self.samples, self.weights))
        total = sum(w for _, w in pairs)
        acc = 0.0
        for f, w in pairs:
            acc += w
            if acc >= q * total:
                return f
        return pairs[-1][0]

    @property
    def low(self) -> float:
        return round(self._quantile(0.1), 2)

    @property
    def high(self) -> float:
        return round(self._quantile(0.9), 2)

    @property
    def best_guess(self) -> float:
        total = sum(self.weights)
        return round(sum(f * w for f, w in zip(self.samples, self.weights)) / total, 2)

    def sample(self, k: int) -> list[float]:
        """Draw k plausible floors (standard terms) for look-ahead search."""
        return self._rng.choices(self.samples, weights=self.weights, k=k)

    def summary(self) -> dict:
        return {"low": self.low, "high": self.high, "best_guess": self.best_guess}
