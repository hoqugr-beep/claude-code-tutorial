"""The quantitative baseline: a zero-drift lognormal random walk.

Why zero drift by default
-------------------------
The tempting move is to measure a stock's recent average daily return and
extrapolate it. Over the horizons this tool covers, that average is
overwhelmingly noise: the standard error of a drift estimate from ``n`` daily
returns is roughly ``sigma / sqrt(n)``, which for a year of data is about the
same size as any plausible drift. Extrapolating it manufactures confident
nonsense. So the baseline assumes the best estimate of tomorrow's price is
today's price, and spends its effort on the *width* of the distribution,
which can actually be estimated from data.

Any directional view therefore has to come from the research layer, be
explicitly bounded, and be shown to the user as a named adjustment.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Sequence

from .errors import MarketDataError

__all__ = [
    "log_returns",
    "realized_volatility",
    "ewma_volatility",
    "VolatilityEstimate",
    "estimate_volatility",
    "Distribution",
    "build_distribution",
    "norm_cdf",
]

TRADING_DAYS_PER_YEAR = 252


def norm_cdf(x: float) -> float:
    """Standard normal CDF, via the error function in the stdlib."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def log_returns(closes: Sequence[float]) -> list[float]:
    """Daily log returns from a close series, skipping non-positive prices."""
    out: list[float] = []
    for previous, current in zip(closes, closes[1:]):
        if previous > 0 and current > 0:
            out.append(math.log(current / previous))
    return out


def realized_volatility(returns: Sequence[float]) -> float:
    """Sample standard deviation of daily log returns."""
    if len(returns) < 2:
        raise MarketDataError("Need at least 2 returns to estimate volatility.")
    return statistics.stdev(returns)


def ewma_volatility(returns: Sequence[float], lam: float = 0.94) -> float:
    """Exponentially weighted daily volatility.

    ``lam`` is the RiskMetrics decay factor: 0.94 is the conventional daily
    value, giving recent sessions more weight so the estimate reacts to a
    volatility regime change instead of averaging it away.
    """
    if len(returns) < 2:
        raise MarketDataError("Need at least 2 returns to estimate volatility.")
    if not 0.0 < lam < 1.0:
        raise ValueError("lam must lie strictly between 0 and 1.")

    variance = statistics.pvariance(returns[: min(len(returns), 20)])
    for r in returns:
        variance = lam * variance + (1.0 - lam) * r * r
    return math.sqrt(variance)


@dataclass(frozen=True)
class VolatilityEstimate:
    """Daily volatility from two estimators, plus the one actually used."""

    realized_daily: float
    ewma_daily: float
    daily: float
    lookback_days: int
    method: str

    @property
    def annualized(self) -> float:
        return self.daily * math.sqrt(TRADING_DAYS_PER_YEAR)


def estimate_volatility(
    closes: Sequence[float], lookback: int = 252, method: str = "max"
) -> VolatilityEstimate:
    """Estimate daily volatility from the most recent ``lookback`` closes.

    ``method`` selects which estimator wins: ``realized``, ``ewma``, or
    ``max`` (the default). ``max`` is deliberately conservative — when the
    two disagree, the wider one is used, because an interval that is too
    narrow is the more damaging error for a forecast.
    """
    window = list(closes[-(lookback + 1):]) if lookback > 0 else list(closes)
    returns = log_returns(window)
    if len(returns) < 20:
        raise MarketDataError(
            f"Only {len(returns)} usable daily returns; need at least 20 for a "
            "volatility estimate worth reporting."
        )

    realized = realized_volatility(returns)
    ewma = ewma_volatility(returns)
    chosen = {
        "realized": realized,
        "ewma": ewma,
        "max": max(realized, ewma),
    }.get(method)
    if chosen is None:
        raise ValueError(f"Unknown volatility method {method!r}.")

    return VolatilityEstimate(
        realized_daily=realized,
        ewma_daily=ewma,
        daily=chosen,
        lookback_days=len(returns),
        method=method,
    )


@dataclass(frozen=True)
class Distribution:
    """A lognormal distribution for the price at the target date.

    ``log S_T ~ Normal(log S_0 + mu, sigma^2)``, so ``median = S_0 * e^mu``.
    ``mu`` is zero for the pure baseline and non-zero only when the research
    layer supplies a bounded directional view.
    """

    spot: float
    mu: float
    sigma: float
    trading_days: int

    @property
    def median(self) -> float:
        return self.spot * math.exp(self.mu)

    @property
    def mean(self) -> float:
        """Expected price. Exceeds the median by the usual lognormal skew."""
        return self.spot * math.exp(self.mu + 0.5 * self.sigma**2)

    def quantile(self, p: float) -> float:
        """The price at cumulative probability ``p`` (0 < p < 1)."""
        if not 0.0 < p < 1.0:
            raise ValueError("p must lie strictly between 0 and 1.")
        return self.spot * math.exp(self.mu + self.sigma * _inverse_norm_cdf(p))

    def interval(self, confidence: float = 0.80) -> tuple[float, float]:
        """Central interval covering ``confidence`` of the distribution.

        Derived from ``quantile`` rather than a table of z-scores, so the
        interval endpoints and the quantiles can never drift apart.
        """
        if not 0.0 < confidence < 1.0:
            raise ValueError("confidence must lie strictly between 0 and 1.")
        tail = (1.0 - confidence) / 2.0
        return self.quantile(tail), self.quantile(1.0 - tail)

    def probability_above(self, price: float) -> float:
        """P(price at target date > ``price``)."""
        if price <= 0:
            return 1.0
        z = (math.log(price / self.spot) - self.mu) / self.sigma
        return 1.0 - norm_cdf(z)

    @property
    def probability_up(self) -> float:
        """P(closing above today's price at the target date)."""
        return self.probability_above(self.spot)


def _inverse_norm_cdf(p: float) -> float:
    """Inverse standard normal CDF (Acklam's rational approximation).

    Accurate to roughly 1.15e-9 in relative error across the full range,
    which is far finer than anything else in this model.
    """
    a = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
    b = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00)
    low, high = 0.02425, 1 - 0.02425

    if p < low:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
               ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
    if p > high:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q + c[1])*q + c[2])*q + c[3])*q + c[4])*q + c[5]) / \
                ((((d[0]*q + d[1])*q + d[2])*q + d[3])*q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r + a[1])*r + a[2])*r + a[3])*r + a[4])*r + a[5])*q / \
           (((((b[0]*r + b[1])*r + b[2])*r + b[3])*r + b[4])*r + 1)


def build_distribution(
    spot: float,
    daily_volatility: float,
    trading_days: int,
    log_drift: float = 0.0,
    volatility_multiplier: float = 1.0,
) -> Distribution:
    """Scale a daily volatility to the horizon and build the distribution.

    Volatility scales with the square root of time, which assumes returns are
    serially uncorrelated. That assumption is imperfect but is the standard
    baseline, and errs toward understating risk during trending markets.
    """
    if spot <= 0:
        raise ValueError("spot price must be positive.")
    if daily_volatility <= 0:
        raise ValueError("daily volatility must be positive.")
    if volatility_multiplier <= 0:
        raise ValueError("volatility multiplier must be positive.")

    days = max(1, int(trading_days))
    sigma = daily_volatility * math.sqrt(days) * volatility_multiplier
    return Distribution(spot=spot, mu=log_drift, sigma=sigma, trading_days=days)
