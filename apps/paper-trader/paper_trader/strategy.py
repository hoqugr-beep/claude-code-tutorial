"""The trading logic the autonomous agent runs.

One ensemble, two modes.  A regime test decides whether the market is
trending or chopping, and the weights on the sub-signals switch accordingly:

* **Trend mode** — EMA spread, Donchian breakout and normalised momentum.
* **Chop mode** — mean reversion on the z-score and RSI, with momentum kept
  at a small weight so a genuine breakout still drags the score.

A small funding tilt leans against crowded positioning (when longs are paying
a lot of funding, being long is more expensive and more crowded).

The output is a single score in [-1, +1].  Sign is direction, magnitude is
conviction, and conviction scales position size.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .indicators import Features


TREND_THRESHOLD = 0.85          # |ema spread / atr| above this = trending
FLIP_THRESHOLD = 0.55           # opposite score this strong closes a position


@dataclass
class Signal:
    score: float
    mode: str
    rationale: str
    components: dict[str, float]

    @property
    def side(self) -> int:
        return 1 if self.score > 0 else -1


def _clamp(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def evaluate(
    f: Features,
    funding_rate: float,
    mom_bars: int = 36,
    trend_threshold: float = TREND_THRESHOLD,
) -> Signal:
    """Score one symbol from its current features."""

    if not f.ready:
        return Signal(0.0, "warmup", "indicators still warming up", {})

    trend = math.tanh(f.trend_strength / 1.5)

    breakout = 0.0
    if f.donchian_high > 0 and f.close > f.donchian_high:
        breakout = 1.0
    elif f.donchian_low > 0 and f.close < f.donchian_low:
        breakout = -1.0

    scale = f.realised_vol * math.sqrt(mom_bars)
    momentum = math.tanh(f.roc / scale) if scale > 0 else 0.0

    z_rev = -math.tanh(f.zscore / 2.0)
    rsi_rev = -_clamp((f.rsi - 50.0) / 30.0)
    funding_tilt = -math.tanh(funding_rate / 0.0006)

    trending = abs(f.trend_strength) > trend_threshold or breakout != 0.0
    if trending:
        mode = "trend"
        score = 0.40 * trend + 0.30 * breakout + 0.30 * momentum + 0.08 * funding_tilt
        why = (
            f"trend mode: ema spread {f.trend_strength:+.2f} ATR, "
            f"breakout {breakout:+.0f}, momentum {momentum:+.2f}"
        )
    else:
        mode = "chop"
        score = 0.50 * z_rev + 0.35 * rsi_rev + 0.15 * momentum + 0.05 * funding_tilt
        why = (
            f"chop mode: z {f.zscore:+.2f}, RSI {f.rsi:.0f}, "
            f"momentum {momentum:+.2f}"
        )

    # A volatility surge makes the estimate less reliable; shade conviction.
    if f.atr_pct > 0.012:
        score *= 0.75
        why += f"; volatility elevated (ATR {100 * f.atr_pct:.2f}% of price), conviction shaded"

    components = {
        "trend": trend,
        "breakout": breakout,
        "momentum": momentum,
        "z_reversion": z_rev,
        "rsi_reversion": rsi_rev,
        "funding_tilt": funding_tilt,
    }
    return Signal(_clamp(score), mode, why, components)


def conviction(score: float, min_signal: float) -> float:
    """Map |score| onto a 0.40-1.00 size multiplier."""
    span = max(1e-9, 1.0 - min_signal)
    raw = (abs(score) - min_signal) / span
    return 0.40 + 0.60 * _clamp(raw, 0.0, 1.0)


def leverage_for_stop(price: float, stop_distance: float, maintenance_margin: float,
                      buffer: float = 1.6, cap: float = 20.0) -> float:
    """Pick per-position leverage so the stop sits well inside liquidation.

    Margin per unit is set so the liquidation price is `buffer` times the stop
    distance away from entry.  Without this, high leverage puts liquidation
    *inside* the stop and the risk model becomes fiction: the position dies
    before its stop can ever fire.
    """
    per_unit_margin = buffer * stop_distance + price * maintenance_margin
    if per_unit_margin <= 0:
        return 1.0
    return max(1.0, min(cap, price / per_unit_margin))
