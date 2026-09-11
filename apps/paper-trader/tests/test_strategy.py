"""Strategy and agent-level behaviour."""

import math
import unittest
from dataclasses import replace

from paper_trader.agent import run_simulation
from paper_trader.config import (BALANCED, DEFAULT_UNIVERSE, SimConfig,
                                 ULTRA_AGGRESSIVE, VenueConfig)
from paper_trader.indicators import Features
from paper_trader.market import generate_market
from paper_trader.metrics import summarize
from paper_trader.strategy import conviction, evaluate, leverage_for_stop
from paper_trader.trend_filter import FilterConfig, run_filter_simulation


def features(**kw) -> Features:
    f = Features(ready=True, close=100.0, atr=1.0, atr_pct=0.01,
                 ema_fast=100.0, ema_slow=100.0, realised_vol=0.002)
    for k, v in kw.items():
        setattr(f, k, v)
    return f


class TestSignal(unittest.TestCase):
    def test_warmup_produces_no_signal(self):
        self.assertEqual(evaluate(Features(ready=False), 0.0).score, 0.0)

    def test_uptrend_scores_positive_and_downtrend_negative(self):
        up = evaluate(features(trend_strength=2.5, roc=0.02), 0.0)
        down = evaluate(features(trend_strength=-2.5, roc=-0.02), 0.0)
        self.assertGreater(up.score, 0)
        self.assertLess(down.score, 0)
        self.assertEqual(up.mode, "trend")

    def test_quiet_market_uses_mean_reversion(self):
        sig = evaluate(features(trend_strength=0.1, zscore=2.5, rsi=78.0), 0.0)
        self.assertEqual(sig.mode, "chop")
        self.assertLess(sig.score, 0, "stretched price should lean short in chop mode")

    def test_breakout_forces_trend_mode(self):
        sig = evaluate(features(trend_strength=0.0, donchian_high=99.0, close=100.0), 0.0)
        self.assertEqual(sig.mode, "trend")

    def test_score_is_bounded(self):
        for kw in ({"trend_strength": 99, "roc": 9}, {"trend_strength": -99, "roc": -9}):
            self.assertLessEqual(abs(evaluate(features(**kw), 0.0).score), 1.0)

    def test_positive_funding_leans_short(self):
        base = evaluate(features(trend_strength=0.2), 0.0).score
        costly = evaluate(features(trend_strength=0.2), 0.003).score
        self.assertLess(costly, base)

    def test_high_volatility_shades_conviction(self):
        calm = evaluate(features(trend_strength=2.0, roc=0.02, atr_pct=0.005), 0.0)
        wild = evaluate(features(trend_strength=2.0, roc=0.02, atr_pct=0.03), 0.0)
        self.assertLess(abs(wild.score), abs(calm.score))

    def test_conviction_is_monotone_and_bounded(self):
        vals = [conviction(x, 0.3) for x in (0.3, 0.5, 0.8, 1.0)]
        self.assertEqual(vals, sorted(vals))
        self.assertAlmostEqual(vals[0], 0.40, places=6)
        self.assertLessEqual(vals[-1], 1.0)


class TestLeverageRule(unittest.TestCase):
    def test_stop_sits_inside_liquidation(self):
        """The core risk-model requirement: the stop must fire before liquidation.

        Otherwise the position dies before its own risk control can act, and
        every number the risk model produces is fiction.
        """
        mm = 0.005
        for stop_pct in (0.002, 0.01, 0.05):
            with self.subTest(stop_pct=stop_pct):
                price, stop_dist = 100.0, 100.0 * stop_pct
                lev = leverage_for_stop(price, stop_dist, mm, cap=20.0)
                per_unit_margin = price / lev
                liq = (price - per_unit_margin) / (1.0 - mm)
                self.assertLess(liq, price - stop_dist,
                                "liquidation must be further away than the stop")

    def test_leverage_is_capped(self):
        self.assertLessEqual(leverage_for_stop(100.0, 0.001, 0.005, cap=7.0), 7.0)


class TestAgentRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = SimConfig(days=8, seed=42, predictability=0.5)
        cls.result = run_simulation(cls.cfg)

    def test_curves_cover_every_bar(self):
        for curve in (self.result.equity_curve, self.result.cash_curve,
                      self.result.leverage_curve):
            self.assertEqual(len(curve), self.cfg.bars)

    def test_equity_never_goes_negative(self):
        self.assertGreaterEqual(min(self.result.equity_curve), 0.0)
        self.assertGreaterEqual(self.result.account.cash, 0.0)

    def test_all_positions_closed_at_the_end(self):
        self.assertEqual(self.result.account.positions, {})

    def test_final_equity_is_all_cash(self):
        self.assertAlmostEqual(self.result.equity_curve[-1],
                               self.result.account.cash, places=6)

    def test_ledger_ties_out(self):
        """Starting cash plus every realised P&L must equal final equity."""
        realised = sum(t.net_pnl for t in self.result.trades)
        self.assertAlmostEqual(
            self.cfg.risk.starting_cash + realised,
            self.result.equity_curve[-1],
            places=6,
        )

    def test_run_is_deterministic(self):
        again = run_simulation(self.cfg)
        self.assertEqual(again.equity_curve, self.result.equity_curve)

    def test_drawdown_circuit_breaker_stops_trading(self):
        risk = replace(ULTRA_AGGRESSIVE, max_drawdown_stop=0.05)
        r = run_simulation(SimConfig(days=10, seed=3, predictability=0.0, risk=risk))
        if r.halted_at is not None:
            self.assertEqual(r.account.positions, {})
            tail = r.equity_curve[r.halted_at + 1:]
            if tail:
                self.assertAlmostEqual(min(tail), max(tail), places=6,
                                       msg="equity must be flat after the halt")

    def test_journal_is_written(self):
        kinds = {j.kind for j in self.result.journal}
        self.assertIn("start", kinds)
        self.assertIn("end", kinds)


class TestFilterAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg = SimConfig(days=12, seed=9, predictability=1.0)
        cls.filt = FilterConfig(target_vol=1.0)
        cls.result = run_filter_simulation(cls.cfg, cls.filt)

    def test_ledger_ties_out(self):
        realised = sum(t.net_pnl for t in self.result.trades)
        self.assertAlmostEqual(
            self.filt.starting_cash + realised, self.result.equity_curve[-1], places=6
        )

    def test_gross_leverage_respects_the_cap(self):
        # A little slack: leverage is set at rebalance and drifts with price
        # between rebalances.
        self.assertLess(max(self.result.leverage_curve), self.filt.max_leverage * 1.6)

    def test_it_actually_takes_positions(self):
        self.assertGreater(len(self.result.trades), 0)
        self.assertGreater(max(self.result.leverage_curve), 0.1)

    def test_higher_volatility_target_produces_more_exposure(self):
        lo = run_filter_simulation(self.cfg, FilterConfig(target_vol=0.25))
        hi = run_filter_simulation(self.cfg, FilterConfig(target_vol=2.0))
        self.assertGreater(
            sum(hi.leverage_curve) / len(hi.leverage_curve),
            sum(lo.leverage_curve) / len(lo.leverage_curve),
        )


class TestRiskPresets(unittest.TestCase):
    def test_balanced_takes_less_risk_than_ultra_aggressive(self):
        self.assertLess(BALANCED.risk_per_trade, ULTRA_AGGRESSIVE.risk_per_trade)
        self.assertLess(BALANCED.max_leverage, ULTRA_AGGRESSIVE.max_leverage)
        self.assertLess(BALANCED.max_drawdown_stop, ULTRA_AGGRESSIVE.max_drawdown_stop)

    def test_balanced_really_does_run_at_lower_leverage(self):
        cfg = SimConfig(days=10, seed=21, predictability=0.5)
        agg = summarize(run_simulation(cfg))
        bal = summarize(run_simulation(replace(cfg, risk=BALANCED)))
        self.assertLess(bal.avg_leverage, agg.avg_leverage)


if __name__ == "__main__":
    unittest.main()
