"""Shared serialisation so the CLI, JSON output and web UI agree."""

from __future__ import annotations

from typing import Any

from .predict import DISCLAIMER, Forecast

__all__ = ["as_dict"]


def as_dict(result: Forecast) -> dict[str, Any]:
    """A plain-data view of a forecast, safe to serialise to JSON."""
    low80, high80 = result.interval(0.80)
    low95, high95 = result.interval(0.95)
    research = result.research

    return {
        "ticker": result.query.ticker,
        "as_of": result.query.as_of.isoformat(),
        "target_date": result.query.target_date.isoformat(),
        "horizon": result.query.horizon_label,
        "trading_days": result.query.trading_days,
        "spot": round(result.spot, 4),
        "last_close_date": result.last_close_date.isoformat(),
        "data_source": result.history.source,
        "point_estimate": round(result.point_estimate, 2),
        "expected_change_pct": round(result.expected_change_pct, 2),
        "probability_up": round(result.probability_up, 4),
        "interval_80": [round(low80, 2), round(high80, 2)],
        "interval_95": [round(low95, 2), round(high95, 2)],
        "volatility": {
            "daily": round(result.volatility.daily, 6),
            "annualized": round(result.volatility.annualized, 4),
            "realized_daily": round(result.volatility.realized_daily, 6),
            "ewma_daily": round(result.volatility.ewma_daily, 6),
            "method": result.volatility.method,
            "lookback_days": result.volatility.lookback_days,
        },
        "horizon_sigma": round(result.distribution.sigma, 6),
        "baseline_sigma": round(result.baseline.sigma, 6),
        "applied_log_drift": round(result.applied_log_drift, 6),
        "bias_was_capped": result.bias_was_capped,
        "research_verified": result.research_verified,
        "research_error": result.research_error,
        "research": (
            {
                "searches_performed": research.searches_performed,
                "expected_move_pct": research.expected_move_pct,
                "confidence": research.confidence,
                "volatility_multiplier": research.volatility_multiplier,
                "narrative": research.narrative,
                "scheduled_events": research.scheduled_events,
                "model": research.model,
                "cost_usd": research.cost_usd,
                "catalysts": [
                    {
                        "category": c.category,
                        "headline": c.headline,
                        "direction": c.direction,
                        "importance": c.importance,
                        "source_url": c.source_url,
                    }
                    for c in research.catalysts
                ],
            }
            if research is not None
            else None
        ),
        "warnings": list(result.warnings),
        "disclaimer": DISCLAIMER,
    }
