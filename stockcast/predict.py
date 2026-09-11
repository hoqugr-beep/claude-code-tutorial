"""Combine the quantitative baseline with verified research into a forecast.

The blend is deliberately lopsided. The statistical model owns the *shape* of
the distribution; research is only allowed to nudge its centre and widen its
spread, within hard caps. Two mechanisms keep the narrative honest:

  shrink  the model's stated directional view is multiplied by its own stated
          confidence, so a hedged view moves the forecast very little;
  cap     the result is then clipped to at most ``MAX_BIAS_SIGMAS`` times the
          horizon's own standard deviation, so no story, however emphatic,
          can move the median further than ordinary noise would.

The point of the caps is that the failure mode of narrative-driven forecasting
is over-confidence, and the caps bind exactly when over-confidence is worst.
"""

from __future__ import annotations

import datetime as _dt
import math
from dataclasses import dataclass, field

from .errors import ResearchError
from .market import PriceHistory, get_history
from .parse import Query, parse_request
from .quant import (
    Distribution,
    VolatilityEstimate,
    build_distribution,
    estimate_volatility,
)
from .research import MAX_BIAS_SIGMAS, ResearchResult, research_ticker

__all__ = ["Forecast", "forecast", "DISCLAIMER"]

DISCLAIMER = (
    "This is a probabilistic model, not investment advice. Short-horizon "
    "stock prices are close to a random walk: the interval is the forecast, "
    "and the single number is only its midpoint. Prices routinely land "
    "outside even a 95% interval when something genuinely unexpected happens."
)


@dataclass
class Forecast:
    """Everything the tool concluded, and how it got there."""

    query: Query
    history: PriceHistory
    volatility: VolatilityEstimate
    baseline: Distribution
    distribution: Distribution
    research: ResearchResult | None = None
    research_error: str | None = None
    applied_log_drift: float = 0.0
    bias_was_capped: bool = False
    warnings: list[str] = field(default_factory=list)

    # -- headline numbers ---------------------------------------------------

    @property
    def spot(self) -> float:
        return self.distribution.spot

    @property
    def point_estimate(self) -> float:
        """The median of the forecast distribution."""
        return self.distribution.median

    @property
    def expected_change_pct(self) -> float:
        return (self.point_estimate / self.spot - 1.0) * 100.0

    @property
    def probability_up(self) -> float:
        return self.distribution.probability_up

    def interval(self, confidence: float = 0.80) -> tuple[float, float]:
        return self.distribution.interval(confidence)

    @property
    def research_verified(self) -> bool:
        return self.research is not None and self.research.verified

    @property
    def last_close_date(self) -> _dt.date:
        return self.history.last.date

    @property
    def data_is_stale(self) -> bool:
        """True if the newest bar predates the request by over a week."""
        return (self.query.as_of - self.last_close_date).days > 7


def _blend(
    baseline_sigma: float, research: ResearchResult | None
) -> tuple[float, bool, float]:
    """Return (applied log drift, whether the cap bound, volatility multiplier)."""
    if research is None or not research.verified:
        return 0.0, False, 1.0

    raw = math.log1p(research.expected_move_pct / 100.0)
    shrunk = raw * research.confidence
    cap = MAX_BIAS_SIGMAS * baseline_sigma
    applied = max(-cap, min(cap, shrunk))
    capped = abs(shrunk) > cap + 1e-12
    return applied, capped, research.volatility_multiplier


def forecast(
    request: str,
    as_of: _dt.date | None = None,
    use_research: bool = True,
    lookback: int = 252,
    volatility_method: str = "max",
    providers: tuple[str, ...] | None = None,
    research_model: str = "sonnet",
    research_timeout: int = 420,
    use_cache: bool = True,
) -> Forecast:
    """Produce a forecast for a request such as ``ORCL 1 week from today``.

    Research failures never fail the forecast: the tool falls back to the
    quantitative baseline and records why in ``research_error``, so the
    output always says whether current events were actually consulted.
    """
    query = parse_request(request, as_of)

    history = (
        get_history(query.ticker, providers=providers, use_cache=use_cache)
        if providers
        else get_history(query.ticker, use_cache=use_cache)
    )

    volatility = estimate_volatility(
        history.closes, lookback=lookback, method=volatility_method
    )
    spot = history.last.close

    baseline = build_distribution(
        spot=spot,
        daily_volatility=volatility.daily,
        trading_days=query.trading_days,
    )

    research: ResearchResult | None = None
    research_error: str | None = None
    if use_research:
        try:
            research = research_ticker(
                query.ticker,
                query.horizon_label,
                query.target_date.isoformat(),
                model=research_model,
                timeout=research_timeout,
            )
        except ResearchError as exc:
            research_error = str(exc)

    drift, capped, vol_multiplier = _blend(baseline.sigma, research)

    distribution = build_distribution(
        spot=spot,
        daily_volatility=volatility.daily,
        trading_days=query.trading_days,
        log_drift=drift,
        volatility_multiplier=vol_multiplier,
    )

    result = Forecast(
        query=query,
        history=history,
        volatility=volatility,
        baseline=baseline,
        distribution=distribution,
        research=research,
        research_error=research_error,
        applied_log_drift=drift,
        bias_was_capped=capped,
    )

    # Warnings the reader needs in order to discount the output correctly.
    if result.data_is_stale:
        result.warnings.append(
            f"Latest price bar is {history.last.date} — "
            f"{(query.as_of - history.last.date).days} days old."
        )
    if research_error:
        result.warnings.append(
            "Fell back to the quantitative baseline; current events were NOT "
            f"consulted. Reason: {research_error}"
        )
    if capped:
        result.warnings.append(
            "The research view was stronger than this horizon's own volatility "
            "and was capped."
        )
    if query.trading_days > 126:
        result.warnings.append(
            f"A {query.trading_days}-session horizon is long enough that the "
            "interval spans most plausible outcomes and says very little."
        )
    if query.rolled_from:
        result.warnings.append(
            f"{query.rolled_from} is not a trading day; forecasting the next "
            f"session, {query.target_date}."
        )
    return result
