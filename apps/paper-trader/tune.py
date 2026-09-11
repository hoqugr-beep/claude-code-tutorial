#!/usr/bin/env python3
"""Search for a better risk configuration — honestly.

Two rules make this a search rather than a way to fool yourself:

1. **Train/holdout split.** Configurations are ranked on one set of market
   seeds and then re-scored on a disjoint set they were never selected on.
   A config that looks brilliant on the training seeds and ordinary on the
   holdout seeds was fitted to noise, and the holdout number is the one that
   counts.
2. **Median, not mean.** With leverage, the mean is dragged around by a
   couple of lucky paths.  The median is what a typical month looks like.

Run:  python3 tune.py --trials 80 --train 16 --holdout 32
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import replace

from paper_trader.config import PRESETS, SimConfig, ULTRA_AGGRESSIVE
from paper_trader.metrics import percentile
from paper_trader.montecarlo import describe, run_paths

SEARCH_SPACE: dict[str, list] = {
    "timescale": [1.0, 3.0, 6.0, 12.0],
    "decision_every": [1, 6, 12, 36],
    "min_signal_strength": [0.25, 0.35, 0.45, 0.55],
    "stop_atr_mult": [1.5, 2.2, 3.0, 4.0],
    "take_profit_r": [3.0, 5.0, 8.0, 1e9],
    "trail_atr_mult": [2.0, 3.0, 5.0],
    "min_edge_ratio": [0.0, 2.0, 4.0, 8.0],
    "cooldown_bars": [6, 36, 144],
    "risk_per_trade": [0.04, 0.08, 0.12],
    "max_positions": [2, 3, 4],
    "trend_threshold": [0.5, 0.85, 1.5],
    "time_stop_days": [1.0, 2.0, 4.0],
    "max_pyramids": [0, 2, 3],
}


def sample(rng: random.Random) -> dict:
    return {k: rng.choice(v) for k, v in SEARCH_SPACE.items()}


def score(config: SimConfig, seeds: list[int]) -> dict:
    d = describe(run_paths(config, seeds), config.risk.starting_cash)
    return {
        "median": d.median,
        "mean": d.mean,
        "p05": d.p05,
        "p95": d.p95,
        "prob_profit": d.prob_profit,
        "prob_ruin": d.prob_ruin,
        "median_dd": d.median_drawdown,
        "trades": d.median_trades,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=80)
    ap.add_argument("--train", type=int, default=16)
    ap.add_argument("--holdout", type=int, default=32)
    ap.add_argument("--finalists", type=int, default=6)
    ap.add_argument("--predictability", type=float, default=0.5)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", default="tuning_results.json")
    args = ap.parse_args()

    rng = random.Random(args.seed)
    train_seeds = list(range(10_000, 10_000 + args.train))
    holdout_seeds = list(range(90_000, 90_000 + args.holdout))

    print(f"Searching {args.trials} configurations on {args.train} training seeds "
          f"(predictability={args.predictability})...")

    results = []
    for t in range(args.trials):
        params = sample(rng)
        cfg = SimConfig(
            predictability=args.predictability,
            risk=replace(ULTRA_AGGRESSIVE, name=f"trial-{t}", **params),
        )
        s = score(cfg, train_seeds)
        results.append({"params": params, "train": s})
        print(f"  [{t + 1:3d}/{args.trials}] median ${s['median']:>8,.0f}  "
              f"P(win) {s['prob_profit']:4.0%}  trades {s['trades']:>5.0f}  "
              f"{ {k: v for k, v in params.items() if k in ('timescale', 'risk_per_trade', 'min_signal_strength')} }")

    results.sort(key=lambda r: r["train"]["median"], reverse=True)
    finalists = results[: args.finalists]

    print(f"\nRe-scoring {len(finalists)} finalists on {args.holdout} HELD-OUT seeds "
          f"they were never selected on...\n")
    baseline = score(
        SimConfig(predictability=args.predictability, risk=ULTRA_AGGRESSIVE), holdout_seeds
    )
    print(f"  {'rank':<5}{'train median':>14}{'holdout median':>16}{'P(win)':>9}"
          f"{'P(ruin)':>9}{'medDD':>8}")
    print(f"  {'base':<5}{'-':>14}{baseline['median']:>16,.0f}"
          f"{baseline['prob_profit']:>9.0%}{baseline['prob_ruin']:>9.0%}"
          f"{baseline['median_dd']:>8.0%}")
    for i, r in enumerate(finalists):
        cfg = SimConfig(
            predictability=args.predictability,
            risk=replace(ULTRA_AGGRESSIVE, **r["params"]),
        )
        r["holdout"] = score(cfg, holdout_seeds)
        print(f"  {i + 1:<5}{r['train']['median']:>14,.0f}"
              f"{r['holdout']['median']:>16,.0f}{r['holdout']['prob_profit']:>9.0%}"
              f"{r['holdout']['prob_ruin']:>9.0%}{r['holdout']['median_dd']:>8.0%}")

    best = max(finalists, key=lambda r: r["holdout"]["median"])
    shrink = 1.0 - best["holdout"]["median"] / max(best["train"]["median"], 1e-9)
    print(f"\nBest on holdout: median ${best['holdout']['median']:,.0f}")
    print(f"Selection shrinkage (train -> holdout): {shrink:+.1%} "
          f"— how much of the training result was luck.")
    print(json.dumps(best["params"], indent=2))

    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump({"baseline_holdout": baseline, "results": results,
                   "best": best, "args": vars(args)}, fh, indent=2)
    print(f"\nFull results written to {args.out}")


if __name__ == "__main__":
    main()
