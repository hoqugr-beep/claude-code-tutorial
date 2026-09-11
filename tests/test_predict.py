"""Tests for the blend, and for the end-to-end forecast over fake data."""

import datetime as dt
import math
import random
import unittest
from unittest import mock

from stockcast import predict
from stockcast.errors import ResearchError
from stockcast.market import Bar, PriceHistory
from stockcast.predict import Forecast, _blend, forecast
from stockcast.report import as_dict
from stockcast.research import MAX_BIAS_SIGMAS, ResearchResult

FRIDAY = dt.date(2026, 9, 11)


def fake_history(ticker="ORCL", sigma=0.02, n=300, seed=5, source="fake"):
    random.seed(seed)
    day, price, bars = dt.date(2025, 1, 1), 100.0, []
    while len(bars) < n:
        if day.weekday() < 5:
            price *= math.exp(random.gauss(0.0, sigma))
            bars.append(Bar(day, price, price * 1.01, price * 0.99, price))
        day += dt.timedelta(days=1)
    return PriceHistory(ticker, bars, source)


def verified(**kwargs):
    kwargs.setdefault("searches_performed", 5)
    kwargs.setdefault("ticker", "ORCL")
    return ResearchResult(**kwargs)


class TestBlend(unittest.TestCase):
    SIGMA = 0.05

    def test_no_research_means_no_drift(self):
        self.assertEqual(_blend(self.SIGMA, None), (0.0, False, 1.0))

    def test_unverified_research_is_ignored_entirely(self):
        research = ResearchResult(
            "ORCL", expected_move_pct=9.0, confidence=1.0,
            volatility_multiplier=1.8, searches_performed=0,
        )
        self.assertEqual(_blend(self.SIGMA, research), (0.0, False, 1.0))

    def test_confidence_shrinks_the_view(self):
        full = _blend(self.SIGMA, verified(expected_move_pct=2.0, confidence=1.0))[0]
        half = _blend(self.SIGMA, verified(expected_move_pct=2.0, confidence=0.5))[0]
        self.assertAlmostEqual(half, full / 2, places=12)

    def test_zero_confidence_erases_the_view(self):
        drift, capped, _ = _blend(
            self.SIGMA, verified(expected_move_pct=25.0, confidence=0.0)
        )
        self.assertEqual(drift, 0.0)
        self.assertFalse(capped)

    def test_extreme_view_is_capped_at_one_sigma(self):
        drift, capped, _ = _blend(
            self.SIGMA, verified(expected_move_pct=40.0, confidence=1.0)
        )
        self.assertTrue(capped)
        self.assertAlmostEqual(drift, MAX_BIAS_SIGMAS * self.SIGMA, places=12)

    def test_extreme_bearish_view_is_capped_symmetrically(self):
        drift, capped, _ = _blend(
            self.SIGMA, verified(expected_move_pct=-40.0, confidence=1.0)
        )
        self.assertTrue(capped)
        self.assertAlmostEqual(drift, -MAX_BIAS_SIGMAS * self.SIGMA, places=12)

    def test_modest_view_is_not_capped(self):
        drift, capped, _ = _blend(
            self.SIGMA, verified(expected_move_pct=1.5, confidence=0.3)
        )
        self.assertFalse(capped)
        self.assertAlmostEqual(drift, math.log(1.015) * 0.3, places=12)

    def test_volatility_multiplier_passes_through(self):
        self.assertEqual(_blend(self.SIGMA, verified(volatility_multiplier=1.6))[2], 1.6)

    def test_cap_scales_with_the_horizon(self):
        wide = _blend(0.20, verified(expected_move_pct=40.0, confidence=1.0))[0]
        narrow = _blend(0.02, verified(expected_move_pct=40.0, confidence=1.0))[0]
        self.assertGreater(wide, narrow)


class TestForecastEndToEnd(unittest.TestCase):
    def _run(self, research=None, error=None, request="ORCL 1 week from today",
             **kwargs):
        history = fake_history()
        with mock.patch.object(predict, "get_history", return_value=history):
            if error is not None:
                target = mock.patch.object(
                    predict, "research_ticker", side_effect=ResearchError(error)
                )
            else:
                target = mock.patch.object(
                    predict, "research_ticker", return_value=research
                )
            with target:
                return forecast(request, as_of=FRIDAY,
                                use_research=research is not None or error is not None,
                                **kwargs)

    def test_baseline_only_is_a_pure_random_walk(self):
        result = self._run()
        self.assertFalse(result.research_verified)
        self.assertAlmostEqual(result.point_estimate, result.spot, places=9)
        self.assertAlmostEqual(result.probability_up, 0.5, places=9)
        self.assertEqual(result.applied_log_drift, 0.0)

    def test_interval_brackets_the_median(self):
        result = self._run()
        low, high = result.interval(0.80)
        self.assertLess(low, result.point_estimate)
        self.assertGreater(high, result.point_estimate)

    def test_research_failure_degrades_and_warns_loudly(self):
        result = self._run(error="web search unavailable")
        self.assertFalse(result.research_verified)
        self.assertIn("web search unavailable", result.research_error)
        self.assertTrue(
            any("NOT consulted" in w for w in result.warnings),
            "the user must be told current events were not consulted",
        )
        self.assertAlmostEqual(result.point_estimate, result.spot, places=9)

    def test_verified_research_moves_the_median(self):
        result = self._run(verified(expected_move_pct=3.0, confidence=0.8))
        self.assertTrue(result.research_verified)
        self.assertGreater(result.point_estimate, result.spot)
        self.assertGreater(result.probability_up, 0.5)

    def test_unverified_research_does_not_move_the_median(self):
        result = self._run(
            ResearchResult("ORCL", expected_move_pct=8.0, confidence=1.0,
                           searches_performed=0)
        )
        self.assertFalse(result.research_verified)
        self.assertAlmostEqual(result.point_estimate, result.spot, places=9)

    def test_volatility_multiplier_widens_versus_baseline(self):
        result = self._run(verified(volatility_multiplier=1.8))
        self.assertGreater(result.distribution.sigma, result.baseline.sigma)

    def test_capped_view_is_flagged_to_the_user(self):
        result = self._run(verified(expected_move_pct=50.0, confidence=1.0))
        self.assertTrue(result.bias_was_capped)
        self.assertTrue(any("capped" in w for w in result.warnings))

    def test_stale_price_data_warns(self):
        old = fake_history()
        with mock.patch.object(predict, "get_history", return_value=old):
            result = forecast("ORCL 1 week", as_of=dt.date(2027, 6, 1),
                              use_research=False)
        self.assertTrue(result.data_is_stale)
        self.assertTrue(any("days old" in w for w in result.warnings))

    def test_long_horizon_warns_about_uselessness(self):
        result = self._run(request="ORCL 18 months")
        self.assertTrue(any("says very little" in w for w in result.warnings))

    def test_rolled_weekend_target_is_explained(self):
        result = self._run(request="ORCL tomorrow")
        self.assertTrue(any("not a trading day" in w for w in result.warnings))

    def test_longer_horizons_are_strictly_wider(self):
        week = self._run(request="ORCL 1 week")
        month = self._run(request="ORCL 2 months")
        self.assertGreater(month.distribution.sigma, week.distribution.sigma)


class TestReport(unittest.TestCase):
    def test_dict_is_json_serialisable_and_complete(self):
        import json

        history = fake_history()
        with mock.patch.object(predict, "get_history", return_value=history):
            result = forecast("ORCL 1 week", as_of=FRIDAY, use_research=False)
        payload = as_dict(result)
        json.dumps(payload)  # must not raise
        for key in ("ticker", "point_estimate", "interval_80", "interval_95",
                    "probability_up", "research_verified", "disclaimer",
                    "warnings", "volatility"):
            self.assertIn(key, payload)
        self.assertEqual(payload["ticker"], "ORCL")
        self.assertFalse(payload["research_verified"])
        self.assertEqual(len(payload["interval_80"]), 2)

    def test_disclaimer_is_always_present(self):
        history = fake_history()
        with mock.patch.object(predict, "get_history", return_value=history):
            result = forecast("ORCL 1 week", as_of=FRIDAY, use_research=False)
        self.assertIn("not investment advice", as_dict(result)["disclaimer"])


class TestRenderers(unittest.TestCase):
    def _forecast(self, research=None):
        history = fake_history()
        with mock.patch.object(predict, "get_history", return_value=history):
            with mock.patch.object(predict, "research_ticker", return_value=research):
                return forecast("ORCL 1 week", as_of=FRIDAY,
                                use_research=research is not None)

    def test_text_renderer_states_when_research_was_skipped(self):
        from stockcast.cli import render_text

        output = render_text(self._forecast())
        self.assertIn("NOT CONSULTED", output)
        self.assertIn("ORCL", output)
        self.assertIn("80% interval", output)

    def test_html_renderer_escapes_injected_text(self):
        from stockcast.web import render_html

        research = verified(
            narrative="<script>alert('xss')</script>",
            catalysts=[],
        )
        html = render_html(self._forecast(research))
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)

    def test_html_renderer_includes_the_disclaimer(self):
        from stockcast.web import render_html

        self.assertIn("not investment advice", render_html(self._forecast()))


if __name__ == "__main__":
    unittest.main()
