"""Configuration for the autonomous paper-trading simulation.

Every number in this file is a *modelling assumption*, not a measured fact.
The volatility, drift, fee and funding parameters are order-of-magnitude
estimates chosen to make the simulation behave like a crypto perpetual-futures
venue.  They are NOT calibrated against a verified historical dataset — if you
care about the numbers, replace them with values you have measured yourself
from a primary source (see `README.md`, "Using real data").
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace


# --------------------------------------------------------------------------
# Time
# --------------------------------------------------------------------------

BAR_MINUTES = 5
BARS_PER_HOUR = 60 // BAR_MINUTES
BARS_PER_DAY = 24 * BARS_PER_HOUR          # 288 — crypto trades 24/7
BARS_PER_YEAR = 365 * BARS_PER_DAY         # 105_120
FUNDING_INTERVAL_BARS = 8 * BARS_PER_HOUR  # funding settles every 8h


# --------------------------------------------------------------------------
# Market universe
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class AssetSpec:
    """Parameters for one synthetic perpetual-futures market."""

    symbol: str
    start_price: float
    annual_drift: float      # expected log-drift, before regime effects
    annual_vol: float        # idiosyncratic annualised volatility
    beta: float              # loading on the common crypto market factor
    jump_per_year: float     # Poisson intensity of price jumps
    jump_vol: float          # std-dev of a jump, in log terms
    adv_usd: float           # average daily volume, drives the impact model


# Approximate, unverified stand-ins for real crypto majors + a high-beta alt.
DEFAULT_UNIVERSE: tuple[AssetSpec, ...] = (
    AssetSpec("BTC-PERP", 62_000.0, 0.25, 0.34, 1.00, 14.0, 0.030, 9.0e9),
    AssetSpec("ETH-PERP",  2_950.0, 0.20, 0.46, 1.15, 16.0, 0.038, 4.5e9),
    AssetSpec("SOL-PERP",    148.0, 0.18, 0.72, 1.45, 22.0, 0.060, 1.4e9),
    AssetSpec("DOGE-PERP",   0.132, 0.00, 0.95, 1.70, 30.0, 0.085, 6.0e8),
)


# --------------------------------------------------------------------------
# Venue model
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class VenueConfig:
    """Costs and mechanics of the simulated perpetual-futures exchange."""

    taker_fee: float = 0.00055          # 5.5 bps per side, charged on notional
    base_spread: float = 0.00020        # half-spread paid on every taker fill
    impact_coef: float = 0.35           # slippage = coef * (notional / ADV) ** 0.5
    maintenance_margin: float = 0.005   # 0.5% of notional must remain as equity
    liquidation_penalty: float = 0.0125 # extra fee on the notional when liquidated
    max_leverage: float = 20.0          # venue cap, independent of the strategy cap
    funding_base: float = 0.0001        # 1 bp per 8h baseline (longs pay)
    funding_vol: float = 0.00035        # noise around the baseline
    funding_beta: float = 0.020         # funding leans with the last 24h of price
    min_notional: float = 10.0          # smallest order the venue accepts


# --------------------------------------------------------------------------
# Strategy / risk
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class RiskConfig:
    """How much rope the autonomous agent is given.

    `ULTRA_AGGRESSIVE` is what the brief asked for.  `BALANCED` exists so the
    report can show what the *same* strategy logic does with sane risk — the
    difference between the two is the honest part of this project.
    """

    name: str = "ultra-aggressive"
    starting_cash: float = 1_000.0
    risk_per_trade: float = 0.08        # fraction of equity risked to the stop
    max_leverage: float = 10.0          # strategy-level cap on gross leverage
    max_positions: int = 4
    max_pyramids: int = 3               # extra adds allowed per winning position
    stop_atr_mult: float = 2.2
    trail_atr_mult: float = 3.0
    take_profit_r: float = 6.0          # take profit at N x initial risk
    daily_loss_limit: float = 0.30      # pause for the rest of the day past this
    max_drawdown_stop: float = 0.75     # hard stop: stop trading for good
    min_signal_strength: float = 0.30   # |score| below this is not a trade
    cooldown_bars: int = 6              # bars to wait after closing a symbol
    reserve_cash: float = 0.02          # keep this fraction of equity unmargined
    min_edge_ratio: float = 0.0         # require stop distance >= N x round-trip cost
    timescale: float = 1.0              # multiplies every indicator lookback
    decision_every: int = 1             # only look for new entries every N bars
    trend_threshold: float = 0.85       # |ema spread / atr| above this = trending
    time_stop_days: float = 2.0         # abandon a trade going nowhere after N days
    allow_shorts: bool = True


ULTRA_AGGRESSIVE = RiskConfig()

BALANCED = RiskConfig(
    name="balanced",
    risk_per_trade=0.01,
    max_leverage=2.0,
    max_positions=3,
    max_pyramids=1,
    stop_atr_mult=2.5,
    trail_atr_mult=4.0,
    take_profit_r=4.0,
    daily_loss_limit=0.06,
    max_drawdown_stop=0.25,
    min_signal_strength=0.45,
    cooldown_bars=24,
    reserve_cash=0.35,
    min_edge_ratio=4.0,
    time_stop_days=3.0,
)

PRESETS = {"ultra-aggressive": ULTRA_AGGRESSIVE, "balanced": BALANCED}


@dataclass(frozen=True)
class SimConfig:
    """Everything one simulation run needs.

    `predictability` is the single most important — and least verifiable —
    assumption in this project, so it is an explicit dial rather than
    something buried in the generator.  It is the annualised Sharpe ratio a
    *perfect* forecaster of the latent trend would earn, before costs:

    * ``0.0`` — an efficient market.  Prices are a jump diffusion with no
      exploitable structure, and no technical strategy can have positive
      expectancy once costs are paid.  This is the null hypothesis.
    * ``0.8`` — the default here.  Roughly the gross Sharpe a good systematic
      trend-following programme might target.  Optimistic, not absurd.
    * ``1.5+`` — a market with structure that a retail agent almost certainly
      does not have access to.

    No claim is made about which value matches real crypto markets; the
    report sweeps the dial so you can see how much of the result is the
    strategy and how much is the assumption.
    """

    days: int = 30
    seed: int = 7
    predictability: float = 0.8
    risk: RiskConfig = ULTRA_AGGRESSIVE
    venue: VenueConfig = field(default_factory=VenueConfig)
    universe: tuple[AssetSpec, ...] = DEFAULT_UNIVERSE

    @property
    def bars(self) -> int:
        return self.days * BARS_PER_DAY

    def with_seed(self, seed: int) -> "SimConfig":
        return replace(self, seed=seed)
