"""Run the same agent over many independent market paths.

One backtest on one path tells you almost nothing about a leveraged
strategy: the distribution of outcomes is wide and skewed, so a single run is
a sample of size one drawn from it.  This module draws the distribution.
"""

from __future__ import annotations

import multiprocessing as mp
from dataclasses import dataclass

from .agent import run_simulation
from .config import SimConfig
from .metrics import max_drawdown, percentile, summarize
from .trend_filter import FilterConfig, run_filter_simulation


@dataclass
class PathResult:
    seed: int
    final_equity: float
    total_return: float
    max_drawdown: float
    trades: int
    liquidations: int
    fees: float
    funding: float
    halted: bool
    win_rate: float


def _run_one(args: tuple[SimConfig, int, FilterConfig | None]) -> PathResult:
    config, seed, filt = args
    if filt is None:
        result = run_simulation(config.with_seed(seed))
    else:
        result = run_filter_simulation(config.with_seed(seed), filt)
    s = summarize(result)
    return PathResult(
        seed=seed,
        final_equity=s.final_equity,
        total_return=s.total_return,
        max_drawdown=s.max_drawdown,
        trades=s.trades,
        liquidations=s.liquidations,
        fees=s.fees_paid,
        funding=s.funding_paid,
        halted=s.halted,
        win_rate=s.win_rate,
    )


def run_paths(
    config: SimConfig,
    seeds: list[int],
    workers: int | None = None,
    filt: FilterConfig | None = None,
) -> list[PathResult]:
    """Run one 30-day path per seed, in parallel.

    Pass `filt` to run the volatility-targeted trend agent instead of the
    discrete one.
    """
    jobs = [(config, s, filt) for s in seeds]
    if workers == 1:
        return [_run_one(j) for j in jobs]
    with mp.Pool(processes=workers or mp.cpu_count()) as pool:
        return pool.map(_run_one, jobs, chunksize=1)


@dataclass
class Distribution:
    n: int
    start: float
    median: float
    mean: float
    p05: float
    p25: float
    p75: float
    p95: float
    best: float
    worst: float
    prob_profit: float
    prob_double: float
    prob_ruin: float          # ends below 10% of starting capital
    prob_halt: float
    median_drawdown: float
    worst_drawdown: float
    mean_liquidations: float
    median_trades: float
    mean_fees: float


def describe(paths: list[PathResult], start: float) -> Distribution:
    eq = sorted(p.final_equity for p in paths)
    dds = sorted(p.max_drawdown for p in paths)
    n = len(paths)
    return Distribution(
        n=n,
        start=start,
        median=percentile(eq, 0.50),
        mean=sum(eq) / n,
        p05=percentile(eq, 0.05),
        p25=percentile(eq, 0.25),
        p75=percentile(eq, 0.75),
        p95=percentile(eq, 0.95),
        best=eq[-1],
        worst=eq[0],
        prob_profit=sum(1 for e in eq if e > start) / n,
        prob_double=sum(1 for e in eq if e >= 2 * start) / n,
        prob_ruin=sum(1 for e in eq if e <= 0.10 * start) / n,
        prob_halt=sum(1 for p in paths if p.halted) / n,
        median_drawdown=percentile(dds, 0.50),
        worst_drawdown=dds[-1],
        mean_liquidations=sum(p.liquidations for p in paths) / n,
        median_trades=percentile(sorted(float(p.trades) for p in paths), 0.50),
        mean_fees=sum(p.fees for p in paths) / n,
    )
