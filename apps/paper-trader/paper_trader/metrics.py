"""Performance statistics for a completed run.

A caveat that matters: Sharpe and Sortino here are computed from 5-minute
returns and scaled by sqrt(105,120) to annualise.  Annualising a 30-day
sample this way is standard practice and also statistically fragile — the
standard error on a Sharpe estimated from one month is large, and the number
should be read as a rough shape descriptor, not a precise quantity.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, asdict

from .config import BARS_PER_DAY, BARS_PER_YEAR
from .exchange import Trade


def max_drawdown(curve: list[float]) -> tuple[float, int, int]:
    """Return (max fractional drawdown, peak index, trough index)."""
    peak = curve[0] if curve else 0.0
    peak_i = trough_i = 0
    worst = 0.0
    cur_peak_i = 0
    for i, v in enumerate(curve):
        if v > peak:
            peak, cur_peak_i = v, i
        dd = 1.0 - v / peak if peak > 0 else 0.0
        if dd > worst:
            worst, peak_i, trough_i = dd, cur_peak_i, i
    return worst, peak_i, trough_i


def bar_returns(curve: list[float]) -> list[float]:
    out = []
    for a, b in zip(curve, curve[1:]):
        out.append((b / a - 1.0) if a > 0 else 0.0)
    return out


def _mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _std(xs: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    m = _mean(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (len(xs) - 1))


def sharpe(curve: list[float]) -> float:
    r = bar_returns(curve)
    sd = _std(r)
    return (_mean(r) / sd) * math.sqrt(BARS_PER_YEAR) if sd > 0 else 0.0


def sortino(curve: list[float]) -> float:
    r = bar_returns(curve)
    downside = [x for x in r if x < 0]
    if not downside:
        return 0.0
    dd = math.sqrt(sum(x * x for x in downside) / len(downside))
    return (_mean(r) / dd) * math.sqrt(BARS_PER_YEAR) if dd > 0 else 0.0


def percentile(sorted_values: list[float], p: float) -> float:
    """Linear-interpolated percentile of an already-sorted list."""
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    k = (len(sorted_values) - 1) * p
    lo = math.floor(k)
    hi = math.ceil(k)
    if lo == hi:
        return sorted_values[int(k)]
    return sorted_values[lo] * (hi - k) + sorted_values[hi] * (k - lo)


@dataclass
class Summary:
    starting_equity: float
    final_equity: float
    total_return: float
    max_drawdown: float
    sharpe: float
    sortino: float
    trades: int
    wins: int
    losses: int
    win_rate: float
    profit_factor: float
    expectancy_r: float
    avg_win: float
    avg_loss: float
    best_trade: float
    worst_trade: float
    liquidations: int
    fees_paid: float
    funding_paid: float
    fees_pct_of_start: float
    turnover_notional: float
    avg_leverage: float
    peak_leverage: float
    time_in_market: float
    days_traded: int
    halted: bool
    halt_reason: str

    def as_dict(self) -> dict:
        return asdict(self)


def summarize(result) -> Summary:
    curve = result.equity_curve
    trades: list[Trade] = result.trades
    start = result.config.risk.starting_cash

    wins = [t for t in trades if t.net_pnl > 0]
    losses = [t for t in trades if t.net_pnl <= 0]
    gross_win = sum(t.net_pnl for t in wins)
    gross_loss = -sum(t.net_pnl for t in losses)
    dd, _, _ = max_drawdown(curve)
    lev = [x for x in result.leverage_curve]
    in_market = sum(1 for x in lev if x > 0) / len(lev) if lev else 0.0
    turnover = sum(t.qty * (t.entry_price + t.exit_price) for t in trades)

    return Summary(
        starting_equity=start,
        final_equity=curve[-1] if curve else start,
        total_return=(curve[-1] / start - 1.0) if curve else 0.0,
        max_drawdown=dd,
        sharpe=sharpe(curve),
        sortino=sortino(curve),
        trades=len(trades),
        wins=len(wins),
        losses=len(losses),
        win_rate=len(wins) / len(trades) if trades else 0.0,
        profit_factor=(gross_win / gross_loss) if gross_loss > 0 else float("inf") if gross_win else 0.0,
        expectancy_r=_mean([t.r_multiple for t in trades]),
        avg_win=_mean([t.net_pnl for t in wins]),
        avg_loss=_mean([t.net_pnl for t in losses]),
        best_trade=max((t.net_pnl for t in trades), default=0.0),
        worst_trade=min((t.net_pnl for t in trades), default=0.0),
        liquidations=result.account.liquidations,
        fees_paid=result.account.fees_total,
        funding_paid=result.account.funding_total,
        fees_pct_of_start=result.account.fees_total / start if start else 0.0,
        turnover_notional=turnover,
        avg_leverage=_mean(lev),
        peak_leverage=max(lev) if lev else 0.0,
        time_in_market=in_market,
        days_traded=len(curve) // BARS_PER_DAY,
        halted=result.halted_at is not None,
        halt_reason=result.halt_reason,
    )
