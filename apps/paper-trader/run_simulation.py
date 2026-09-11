#!/usr/bin/env python3
"""Run the autonomous paper-trading simulation and write a report.

    python3 run_simulation.py                       # 30 days, full report
    python3 run_simulation.py --paths 500           # a wider Monte Carlo
    python3 run_simulation.py --preset balanced     # the sane risk settings
    python3 run_simulation.py --predictability 0    # the efficient-market null
    python3 run_simulation.py --quick               # fast, fewer paths

Nothing here connects to a network or places an order. It is a simulation.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from collections import defaultdict
from dataclasses import replace

from paper_trader.agent import run_simulation
from paper_trader.config import PRESETS, SimConfig
from paper_trader.metrics import summarize
from paper_trader.montecarlo import describe, run_paths
from paper_trader.report import ReportData, render
from paper_trader.trend_filter import FilterConfig, run_filter_simulation

BANNER = """
================================================================================
  AUTONOMOUS PAPER TRADING SIMULATION
  Synthetic markets. Simulated money. No orders are placed anywhere.
================================================================================
"""


def money(x: float) -> str:
    return f"${x:,.2f}"


def print_run(result, summary, agent: str = "discrete") -> None:
    cfg = result.config
    print(f"\n  Agent              {agent}")
    print(f"  Preset             {cfg.risk.name}")
    print(f"  Horizon            {cfg.days} days, 24/7, {cfg.bars:,} five-minute decisions")
    print(f"  Predictability     {cfg.predictability:.2f}  "
          f"(0 = efficient market; the load-bearing assumption)")
    print(f"  Market seed        {cfg.seed}")
    print("  " + "-" * 60)
    print(f"  Starting capital   {money(summary.starting_equity)}")
    print(f"  Final equity       {money(summary.final_equity)}   "
          f"({summary.total_return:+.1%})")
    print(f"  Max drawdown       {summary.max_drawdown:.1%}")
    print(f"  Trades             {summary.trades:,}  "
          f"({summary.win_rate:.0%} winners, expectancy {summary.expectancy_r:+.3f}R)")
    print(f"  Fees paid          {money(summary.fees_paid)}  "
          f"({summary.fees_pct_of_start:.0%} of starting capital)")
    print(f"  Funding paid       {money(summary.funding_paid)}")
    print(f"  Liquidations       {summary.liquidations}")
    print(f"  Average leverage   {summary.avg_leverage:.1f}x  (peak {summary.peak_leverage:.1f}x)")
    if result.halted_at is not None:
        print(f"  HALTED             {result.halt_reason}")


def print_distribution(label: str, d) -> None:
    print(f"\n  {label}  ({d.n} independent market paths)")
    print("  " + "-" * 60)
    print(f"  Median outcome     {money(d.median)}")
    print(f"  Mean outcome       {money(d.mean)}")
    print(f"  5th / 95th pct     {money(d.p05)}  /  {money(d.p95)}")
    print(f"  Best / worst       {money(d.best)}  /  {money(d.worst)}")
    print(f"  P(profit)          {d.prob_profit:.0%}")
    print(f"  P(double)          {d.prob_double:.0%}")
    print(f"  P(ruin, <10%)      {d.prob_ruin:.0%}")
    print(f"  Median drawdown    {d.median_drawdown:.0%}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--days", type=int, default=30)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--preset", choices=sorted(PRESETS), default="ultra-aggressive")
    ap.add_argument("--agent", choices=("discrete", "filter"), default="discrete",
                    help="discrete = ultra-aggressive entries and stops; "
                         "filter = volatility-targeted continuous positions")
    ap.add_argument("--target-vol", type=float, default=1.0,
                    help="annualised account volatility target for the filter agent")
    ap.add_argument("--predictability", type=float, default=0.5,
                    help="Sharpe a matched trend filter could extract; 0 = efficient market")
    ap.add_argument("--paths", type=int, default=240, help="Monte Carlo paths")
    ap.add_argument("--sweep-paths", type=int, default=96,
                    help="paths per point in the sensitivity and preset comparisons")
    ap.add_argument("--quick", action="store_true", help="fewer paths, for a fast look")
    ap.add_argument("--report", default="report.html", help="output HTML path ('' to skip)")
    ap.add_argument("--json", default="", help="also write the summary as JSON")
    ap.add_argument("--workers", type=int, default=None)
    args = ap.parse_args(argv)

    if args.quick:
        args.paths = min(args.paths, 48)
        args.sweep_paths = min(args.sweep_paths, 24)

    print(BANNER)
    base = SimConfig(
        days=args.days,
        seed=args.seed,
        predictability=args.predictability,
        risk=replace(PRESETS[args.preset], starting_cash=1_000.0),
    )

    headline_filt = (
        FilterConfig(target_vol=args.target_vol) if args.agent == "filter" else None
    )

    print("[1/6] Running the headline month...")
    result = (
        run_filter_simulation(base, headline_filt) if headline_filt
        else run_simulation(base)
    )
    summary = summarize(result)
    print_run(result, summary, args.agent)

    print(f"\n[2/6] Re-running the same agent over {args.paths} independent months...")
    mc_seeds = list(range(50_000, 50_000 + args.paths))
    paths = run_paths(base, mc_seeds, args.workers, headline_filt)
    dist = describe(paths, base.risk.starting_cash)
    print_distribution("Distribution of 30-day outcomes", dist)

    print("\n[3/6] Sweeping the predictability assumption...")
    sweep_seeds = list(range(60_000, 60_000 + args.sweep_paths))
    sensitivity = []
    print(f"\n  {'dial':>6} {'median':>11} {'5th pct':>11} {'95th pct':>11} "
          f"{'P(profit)':>10} {'P(ruin)':>8}")
    for p in (0.0, 0.25, 0.5, 1.0, 2.0):
        cfg = replace(base, predictability=p)
        d = describe(run_paths(cfg, sweep_seeds, args.workers, headline_filt),
                     base.risk.starting_cash)
        sensitivity.append((p, d))
        print(f"  {p:6.2f} {money(d.median):>11} {money(d.p05):>11} {money(d.p95):>11} "
              f"{d.prob_profit:>10.0%} {d.prob_ruin:>8.0%}")

    print("\n[4/6] Sweeping how much risk to take, at a fixed edge...")
    print("      Expected log growth is  L*S*v - 0.5*(L*v)^2 - costs, so growth peaks")
    print("      where account volatility equals the edge and goes negative past twice it.")
    risk_sweep = []
    print(f"\n  {'target vol':>11} {'median':>11} {'5th pct':>11} {'95th pct':>11} "
          f"{'P(profit)':>10} {'medDD':>7}")
    for tv in (0.25, 0.5, 1.0, 2.0, 4.0):
        d = describe(
            run_paths(base, sweep_seeds, args.workers, FilterConfig(target_vol=tv)),
            base.risk.starting_cash,
        )
        risk_sweep.append((tv, d))
        print(f"  {tv:>10.0%} {money(d.median):>11} {money(d.p05):>11} {money(d.p95):>11} "
              f"{d.prob_profit:>10.0%} {d.median_drawdown:>7.0%}")

    print("\n[5/6] Comparing strategies on identical markets...")
    comparison = []
    print(f"\n  {'strategy':<34} {'median':>11} {'5th pct':>11} {'95th pct':>11} "
          f"{'P(profit)':>10} {'medDD':>7}")
    contenders = [
        ("discrete, ultra-aggressive",
         replace(base, risk=replace(PRESETS["ultra-aggressive"], starting_cash=1_000.0)), None),
        ("discrete, balanced",
         replace(base, risk=replace(PRESETS["balanced"], starting_cash=1_000.0)), None),
        ("vol-targeted filter, 400% vol", base, FilterConfig(target_vol=4.0)),
        ("vol-targeted filter, 100% vol", base, FilterConfig(target_vol=1.0)),
        ("vol-targeted filter, 25% vol", base, FilterConfig(target_vol=0.25)),
    ]
    for name, cfg, filt in contenders:
        d = describe(run_paths(cfg, sweep_seeds, args.workers, filt),
                     base.risk.starting_cash)
        comparison.append((name, d))
        print(f"  {name:<34} {money(d.median):>11} {money(d.p05):>11} {money(d.p95):>11} "
              f"{d.prob_profit:>10.0%} {d.median_drawdown:>7.0%}")

    per_asset: dict[str, float] = defaultdict(float)
    for t in result.trades:
        per_asset[t.symbol.replace("-PERP", "")] += t.net_pnl
    for spec in base.universe:
        per_asset.setdefault(spec.symbol.replace("-PERP", ""), 0.0)

    print("\n[6/6] Rendering the report...")
    if args.report:
        data = ReportData(
            result=result,
            summary=summary,
            distribution=dist,
            path_equities=[p.final_equity for p in paths],
            sensitivity=sensitivity,
            risk_sweep=risk_sweep,
            comparison=comparison,
            per_asset=dict(per_asset),
            generated=dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        with open(args.report, "w", encoding="utf-8") as fh:
            fh.write(render(data))
        print(f"  Wrote {args.report}")

    if args.json:
        payload = {
            "config": {"days": base.days, "seed": base.seed, "preset": args.preset,
                       "predictability": base.predictability},
            "headline": summary.as_dict(),
            "distribution": dist.__dict__,
            "sensitivity": {str(p): d.__dict__ for p, d in sensitivity},
            "risk_sweep": {str(t): d.__dict__ for t, d in risk_sweep},
            "comparison": {n: d.__dict__ for n, d in comparison},
        }
        with open(args.json, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        print(f"  Wrote {args.json}")

    print(f"""
================================================================================
  BOTTOM LINE

  Single month shown above:  {money(summary.final_equity)} ({summary.total_return:+.1%})
  Typical month (median):    {money(dist.median)}
  Chance the month is green: {dist.prob_profit:.0%}
  Chance of near-total loss: {dist.prob_ruin:.0%}

  Best risk level found:     {money(max(risk_sweep, key=lambda r: r[1].median)[1].median)}
                             at a {max(risk_sweep, key=lambda r: r[1].median)[0]:.0%} volatility target

  One run proves nothing. The distribution is the result.
  Simulated throughout — no money was ever at risk.
================================================================================
""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
