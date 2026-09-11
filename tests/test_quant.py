import math
import random
import unittest

from stockcast.errors import MarketDataError
from stockcast.quant import (
    Distribution,
    build_distribution,
    estimate_volatility,
    ewma_volatility,
    log_returns,
    norm_cdf,
    realized_volatility,
)
from stockcast.quant import _inverse_norm_cdf


def gbm(sigma=0.02, n=1500, seed=1, mu=0.0, start=100.0):
    random.seed(seed)
    closes = [start]
    for _ in range(n):
        closes.append(closes[-1] * math.exp(random.gauss(mu, sigma)))
    return closes


class TestNormal(unittest.TestCase):
    def test_cdf_landmarks(self):
        self.assertAlmostEqual(norm_cdf(0.0), 0.5, places=12)
        self.assertAlmostEqual(norm_cdf(1.959964), 0.975, places=6)

    def test_inverse_round_trips(self):
        for p in (1e-6, 0.001, 0.01, 0.1, 0.3, 0.5, 0.7, 0.9, 0.99, 0.999):
            self.assertAlmostEqual(norm_cdf(_inverse_norm_cdf(p)), p, places=8)

    def test_inverse_is_antisymmetric(self):
        for p in (0.01, 0.1, 0.25, 0.4):
            self.assertAlmostEqual(
                _inverse_norm_cdf(p), -_inverse_norm_cdf(1 - p), places=8
            )


class TestReturns(unittest.TestCase):
    def test_log_returns_length_and_value(self):
        returns = log_returns([100.0, 110.0, 121.0])
        self.assertEqual(len(returns), 2)
        for r in returns:
            self.assertAlmostEqual(r, math.log(1.1), places=12)

    def test_skips_non_positive_prices(self):
        self.assertEqual(len(log_returns([100.0, 0.0, 100.0])), 0)

    def test_flat_series_has_zero_volatility(self):
        self.assertAlmostEqual(realized_volatility(log_returns([5.0] * 50)), 0.0)

    def test_too_few_returns_raises(self):
        with self.assertRaises(MarketDataError):
            realized_volatility([0.01])


class TestVolatility(unittest.TestCase):
    def test_recovers_known_volatility(self):
        estimate = estimate_volatility(gbm(sigma=0.02, n=3000), lookback=3000,
                                       method="realized")
        self.assertAlmostEqual(estimate.daily, 0.02, delta=0.002)

    def test_annualisation(self):
        estimate = estimate_volatility(gbm(), lookback=1000, method="realized")
        self.assertAlmostEqual(
            estimate.annualized, estimate.daily * math.sqrt(252), places=12
        )

    def test_max_method_is_the_wider_of_the_two(self):
        estimate = estimate_volatility(gbm(), lookback=500, method="max")
        self.assertEqual(
            estimate.daily, max(estimate.realized_daily, estimate.ewma_daily)
        )

    def test_ewma_tracks_a_regime_change(self):
        # Calm for a long stretch, then a sharp burst of volatility.
        calm = gbm(sigma=0.005, n=600, seed=3)
        loud = gbm(sigma=0.05, n=120, seed=4, start=calm[-1])
        returns = log_returns(calm + loud[1:])
        self.assertGreater(ewma_volatility(returns), realized_volatility(returns))

    def test_rejects_bad_method(self):
        with self.assertRaises(ValueError):
            estimate_volatility(gbm(), method="crystal-ball")

    def test_rejects_too_little_history(self):
        with self.assertRaises(MarketDataError):
            estimate_volatility([100.0, 101.0, 102.0])

    def test_rejects_bad_lambda(self):
        with self.assertRaises(ValueError):
            ewma_volatility([0.01, -0.01, 0.02], lam=1.5)


class TestDistribution(unittest.TestCase):
    def setUp(self):
        self.d = build_distribution(spot=100.0, daily_volatility=0.02,
                                    trading_days=5)

    def test_zero_drift_gives_exactly_even_odds(self):
        self.assertAlmostEqual(self.d.probability_up, 0.5, places=12)
        self.assertAlmostEqual(self.d.median, 100.0, places=12)

    def test_interval_and_quantile_agree_exactly(self):
        # Regression guard: these were once computed two different ways.
        for confidence in (0.5, 0.8, 0.9, 0.95):
            low, high = self.d.interval(confidence)
            tail = (1 - confidence) / 2
            self.assertAlmostEqual(low, self.d.quantile(tail), places=12)
            self.assertAlmostEqual(high, self.d.quantile(1 - tail), places=12)

    def test_wider_confidence_is_a_wider_interval(self):
        narrow = self.d.interval(0.80)
        wide = self.d.interval(0.95)
        self.assertLess(wide[0], narrow[0])
        self.assertGreater(wide[1], narrow[1])

    def test_volatility_scales_as_sqrt_time(self):
        four_x = build_distribution(100.0, 0.02, 20)
        self.assertAlmostEqual(four_x.sigma / self.d.sigma, 2.0, places=12)

    def test_lognormal_mean_exceeds_median(self):
        self.assertGreater(self.d.mean, self.d.median)

    def test_positive_drift_raises_probability_up(self):
        drifted = build_distribution(100.0, 0.02, 5, log_drift=0.02)
        self.assertGreater(drifted.probability_up, self.d.probability_up)
        self.assertGreater(drifted.median, 100.0)

    def test_volatility_multiplier_widens_without_moving_median(self):
        wide = build_distribution(100.0, 0.02, 5, volatility_multiplier=1.5)
        self.assertAlmostEqual(wide.median, self.d.median, places=12)
        self.assertLess(wide.interval(0.8)[0], self.d.interval(0.8)[0])

    def test_probability_above_is_monotonic(self):
        probabilities = [self.d.probability_above(p) for p in (80, 90, 100, 110, 120)]
        self.assertEqual(probabilities, sorted(probabilities, reverse=True))

    def test_quantiles_match_a_simulation(self):
        random.seed(11)
        d = build_distribution(100.0, 0.02, 10)
        draws = sorted(
            d.spot * math.exp(d.mu + d.sigma * random.gauss(0, 1))
            for _ in range(40000)
        )
        for p in (0.1, 0.5, 0.9):
            empirical = draws[int(p * len(draws))]
            self.assertAlmostEqual(d.quantile(p) / empirical, 1.0, delta=0.02)

    def test_rejects_nonsense_inputs(self):
        for kwargs in (
            {"spot": 0.0, "daily_volatility": 0.02, "trading_days": 5},
            {"spot": 100.0, "daily_volatility": 0.0, "trading_days": 5},
            {"spot": 100.0, "daily_volatility": 0.02, "trading_days": 5,
             "volatility_multiplier": 0.0},
        ):
            with self.assertRaises(ValueError):
                build_distribution(**kwargs)

    def test_horizon_floors_at_one_session(self):
        self.assertEqual(build_distribution(100.0, 0.02, 0).trading_days, 1)

    def test_rejects_out_of_range_probabilities(self):
        for bad in (0.0, 1.0, -0.5, 2.0):
            with self.assertRaises(ValueError):
                self.d.quantile(bad)
            with self.assertRaises(ValueError):
                self.d.interval(bad)


if __name__ == "__main__":
    unittest.main()
