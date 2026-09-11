"""Synthetic 24/7 crypto perpetual-futures market generator.

The price process is a regime-switching jump diffusion with a common market
factor, which reproduces the qualitative features that matter for testing an
aggressive leveraged strategy: volatility clustering, trending and chopping
regimes, correlated drawdowns, and fat tails from jumps.

It is *not* a forecast, and it is not fitted to real history.  Treat any P&L
produced on top of it as a property of the model, not of the real market.
`load_csv_market` exists so you can run the same agent on data you trust.
"""

from __future__ import annotations

import csv
import math
import random
from dataclasses import dataclass

from .config import BARS_PER_DAY, BARS_PER_YEAR, AssetSpec, VenueConfig

# Hard cap on any single 8-hourly funding rate (0.30%), matching the clamps
# real venues apply.
FUNDING_CAP = 0.003


@dataclass
class Bar:
    """One OHLC bar plus the funding rate applying to the interval."""

    index: int
    open: float
    high: float
    low: float
    close: float
    volume_usd: float


# Regimes change *volatility only*, never drift.
#
# Volatility clustering is a well-established stylised fact of financial
# returns.  Regime-dependent drift is not — and baking it in quietly creates
# exploitable structure, which would mean the `predictability = 0` setting is
# not actually a null hypothesis.  It has to be one, or the whole sensitivity
# analysis is worthless.
#
# (label, drift multiplier, vol multiplier, mean bars in regime)
REGIMES = (
    ("calm", 1.0, 0.65, 4 * BARS_PER_DAY),
    ("active", 1.0, 1.05, 3 * BARS_PER_DAY),
    ("stress", 1.0, 2.30, 1 * BARS_PER_DAY),
)

# Row i -> probabilities of moving to regime j when the current regime ends.
REGIME_SWITCH = (
    (0.00, 0.72, 0.28),
    (0.55, 0.00, 0.45),
    (0.62, 0.38, 0.00),
)


class Market:
    """A generated multi-asset market: `market.bars[symbol][i]`."""

    def __init__(
        self,
        assets: tuple[AssetSpec, ...],
        bars: dict[str, list[Bar]],
        regimes: list[str],
        funding: dict[str, list[float]],
    ) -> None:
        self.assets = assets
        self.symbols = [a.symbol for a in assets]
        self.spec = {a.symbol: a for a in assets}
        self.bars = bars
        self.regimes = regimes
        self.funding = funding
        self.n_bars = len(next(iter(bars.values())))

    def close(self, symbol: str, i: int) -> float:
        return self.bars[symbol][i].close

    def slice(self, symbol: str, i: int, lookback: int) -> list[Bar]:
        lo = max(0, i - lookback + 1)
        return self.bars[symbol][lo : i + 1]


def _sample_regime_length(rng: random.Random, mean_bars: float) -> int:
    return max(BARS_PER_DAY // 8, int(rng.expovariate(1.0 / mean_bars)))


def _next_regime(rng: random.Random, current: int) -> int:
    r = rng.random()
    acc = 0.0
    for j, p in enumerate(REGIME_SWITCH[current]):
        acc += p
        if r <= acc:
            return j
    return current


MARKET_LATENT_HALFLIFE = 3 * BARS_PER_DAY
ASSET_LATENT_HALFLIFE = 1 * BARS_PER_DAY

# Empirical constant tying the latent-drift gain to the Sharpe a matched
# filter can actually extract.  See `tests/test_market.py::
# TestPredictabilityCalibration`, which measures it back out of generated
# data rather than trusting the algebra.
DRIFT_CALIBRATION = 1.30


def _ar1_phi(half_life_bars: float) -> float:
    return 0.5 ** (1.0 / half_life_bars)


def drift_gain(predictability: float, half_life_bars: float) -> float:
    """Latent-drift coefficient, in units of the asset's own volatility.

    `predictability` is defined as the approximate annualised Sharpe ratio a
    *realistic* filter — an exponential average of past returns matched to
    the latent's half-life — can extract from the price series before costs.

    That is a deliberately different definition from "the Sharpe a perfect
    forecaster would earn".  A perfect forecaster knows the latent state
    exactly; a filter reading prices recovers it only with correlation
    ``rho ~ k * sqrt(H * dt)``, which for a one-day half-life on 5-minute
    bars is a few percent.  Scaling the dial to perfect foresight therefore
    produces a market that looks predictable on paper and is untradeable in
    practice.  Achieved Sharpe goes as ``k**2 * sqrt(H * dt)``, so:

        k = sqrt(predictability / sqrt(H * dt))
    """
    if predictability <= 0.0:
        return 0.0
    h_dt = half_life_bars / BARS_PER_YEAR
    return DRIFT_CALIBRATION * math.sqrt(predictability / math.sqrt(h_dt))


def bridge_extremes(
    log_move: float, bar_vol: float, u: float, v: float
) -> tuple[float, float]:
    """Exact intrabar high/low for a Brownian bridge, in log space.

    For a bridge from 0 to `b` over one bar with volatility `sigma`,
    ``P(max >= m) = exp(-2m(m - b) / sigma**2)`` for ``m >= max(0, b)``.
    Inverting that with a uniform draw gives

        m = (b + sqrt(b**2 - 2 * sigma**2 * ln u)) / 2

    and symmetrically for the minimum.  Sampling the extremes this way keeps
    the intrabar range consistent with the close-to-close volatility the
    generator was asked for.  An ad-hoc wick model does not, and any excess
    range it invents is a free kill on every stop-based strategy tested on
    the data — the backtest then measures the generator's bug.
    """
    b = log_move
    var = max(bar_vol, 1e-12) ** 2
    u = min(max(u, 1e-12), 1.0 - 1e-12)
    v = min(max(v, 1e-12), 1.0 - 1e-12)
    hi = 0.5 * (b + math.sqrt(b * b - 2.0 * var * math.log(u)))
    lo = 0.5 * (b - math.sqrt(b * b - 2.0 * var * math.log(v)))
    return hi, lo


def generate_market(
    assets: tuple[AssetSpec, ...],
    n_bars: int,
    seed: int,
    predictability: float = 0.0,
    venue: "VenueConfig | None" = None,
) -> Market:
    """Generate `n_bars` five-minute bars for every asset in `assets`.

    `predictability` injects a latent, slowly mean-reverting trend into the
    drift of every asset.  It is scaled so that a forecaster with perfect
    knowledge of the latent state would earn approximately this annualised
    Sharpe ratio before costs.  At 0.0 the market is a pure jump diffusion
    with no exploitable structure — the honest null hypothesis.
    """

    rng = random.Random(seed)
    v = venue or VenueConfig()
    dt = 1.0 / BARS_PER_YEAR
    sqrt_dt = math.sqrt(dt)

    # ---- regime path (shared by the whole market) ------------------------
    regime_idx = 0
    remaining = _sample_regime_length(rng, REGIMES[0][3])
    regime_path: list[int] = []
    for _ in range(n_bars):
        if remaining <= 0:
            regime_idx = _next_regime(rng, regime_idx)
            remaining = _sample_regime_length(rng, REGIMES[regime_idx][3])
        regime_path.append(regime_idx)
        remaining -= 1

    # ---- common market factor -------------------------------------------
    factor_vol = 0.55          # annualised vol of the crypto "market"
    factor_drift = 0.20
    factor: list[float] = []
    # Latent market trend: AR(1) with a three-day half-life, unit variance.
    phi_m = _ar1_phi(MARKET_LATENT_HALFLIFE)
    shock_m = math.sqrt(1.0 - phi_m * phi_m)
    gain_m = drift_gain(predictability, MARKET_LATENT_HALFLIFE)
    latent_m = rng.gauss(0.0, 1.0)
    latent_market: list[float] = []
    for i in range(n_bars):
        latent_m = phi_m * latent_m + shock_m * rng.gauss(0.0, 1.0)
        latent_market.append(latent_m)
        _, dmul, vmul, _ = REGIMES[regime_path[i]]
        sig = factor_vol * vmul
        mu = factor_drift * dmul + gain_m * sig * latent_m
        factor.append((mu - 0.5 * sig * sig) * dt + sig * sqrt_dt * rng.gauss(0.0, 1.0))

    # ---- per-asset paths -------------------------------------------------
    bars: dict[str, list[Bar]] = {}
    funding: dict[str, list[float]] = {}

    for spec in assets:
        price = spec.start_price
        series: list[Bar] = []
        rates: list[float] = []
        jump_p = spec.jump_per_year * dt
        # Latent idiosyncratic trend: AR(1) with a one-day half-life.
        phi_a = _ar1_phi(ASSET_LATENT_HALFLIFE)
        shock_a = math.sqrt(1.0 - phi_a * phi_a)
        gain_a = drift_gain(predictability, ASSET_LATENT_HALFLIFE)
        latent_a = rng.gauss(0.0, 1.0)
        for i in range(n_bars):
            _, dmul, vmul, _ = REGIMES[regime_path[i]]
            idio_vol = spec.annual_vol * vmul
            latent_a = phi_a * latent_a + shock_a * rng.gauss(0.0, 1.0)
            mu = spec.annual_drift * dmul + gain_a * idio_vol * latent_a

            ret = spec.beta * factor[i]
            ret += (mu - 0.5 * idio_vol * idio_vol) * dt
            ret += idio_vol * sqrt_dt * rng.gauss(0.0, 1.0)
            if rng.random() < jump_p:
                ret += rng.gauss(0.0, spec.jump_vol) - 0.5 * spec.jump_vol ** 2

            open_ = price
            close = max(1e-9, price * math.exp(ret))

            # Total per-bar volatility, combined in quadrature (the factor and
            # idiosyncratic shocks are independent, so their variances add).
            bar_vol = math.sqrt(
                (spec.beta * factor_vol * vmul) ** 2 + idio_vol ** 2
            ) * sqrt_dt
            hi_log, lo_log = bridge_extremes(
                ret, bar_vol, rng.random(), rng.random()
            )
            high = open_ * math.exp(hi_log)
            low = open_ * math.exp(lo_log)

            turn = spec.adv_usd / BARS_PER_DAY
            volume = turn * math.exp(rng.gauss(0.0, 0.55)) * (1.0 + 2.0 * abs(ret) / max(bar_vol, 1e-9) * 0.25)

            series.append(Bar(i, open_, high, low, close, volume))
            price = close

            # Funding leans with recent positioning: after a sustained rally
            # longs are crowded and pay more.  Magnitudes are deliberately
            # small — real perpetual funding is a handful of basis points per
            # 8h, spiking to a few tenths of a percent in extremes — and the
            # result is clipped so a single violent bar cannot invent a fee
            # larger than the move that caused it.
            day_move = 0.0
            if i >= BARS_PER_DAY:
                day_move = math.log(close / series[i - BARS_PER_DAY].close)
            rate = (
                v.funding_base
                + v.funding_beta * day_move
                + rng.gauss(0.0, v.funding_vol)
            )
            rates.append(max(-FUNDING_CAP, min(FUNDING_CAP, rate)))

        bars[spec.symbol] = series
        funding[spec.symbol] = rates

    return Market(assets, bars, [REGIMES[r][0] for r in regime_path], funding)


def load_csv_market(
    paths: dict[str, str],
    assets: tuple[AssetSpec, ...],
    funding_rate: float = 0.0001,
) -> Market:
    """Load real bars instead of generating them.

    Each CSV must have a header row and the columns
    ``open,high,low,close,volume_usd`` (extra columns are ignored, order does
    not matter).  All files must contain the same number of rows, aligned in
    time — the loader does not resample or join on timestamps, so do that in
    whatever tool exported the data.
    """

    bars: dict[str, list[Bar]] = {}
    funding: dict[str, list[float]] = {}
    for symbol, path in paths.items():
        rows: list[Bar] = []
        with open(path, newline="", encoding="utf-8") as fh:
            for i, row in enumerate(csv.DictReader(fh)):
                rows.append(
                    Bar(
                        i,
                        float(row["open"]),
                        float(row["high"]),
                        float(row["low"]),
                        float(row["close"]),
                        float(row.get("volume_usd", 0.0) or 0.0),
                    )
                )
        if not rows:
            raise ValueError(f"{path} contained no rows")
        bars[symbol] = rows
        funding[symbol] = [funding_rate] * len(rows)

    lengths = {len(v) for v in bars.values()}
    if len(lengths) != 1:
        raise ValueError(f"CSV files have mismatched lengths: {lengths}")

    used = tuple(a for a in assets if a.symbol in bars)
    missing = set(bars) - {a.symbol for a in used}
    if missing:
        raise ValueError(f"no AssetSpec for symbols: {sorted(missing)}")
    return Market(used, bars, ["real"] * len(next(iter(bars.values()))), funding)
