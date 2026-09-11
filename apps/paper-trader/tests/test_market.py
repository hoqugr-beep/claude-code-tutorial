"""The generator is part of the system under test.

If the synthetic market does not have the statistical properties it claims,
every strategy result measured on top of it is measuring the generator's bug.
These tests round-trip the spec: generate data, then measure the parameters
back out of it.
"""

import math
import statistics
import unittest

from paper_trader.config import BARS_PER_YEAR, DEFAULT_UNIVERSE, VenueConfig
from paper_trader.market import FUNDING_CAP, bridge_extremes, generate_market


def log_returns(bars):
    return [math.log(b.close / a.close) for a, b in zip(bars, bars[1:])]


class TestBrownianBridge(unittest.TestCase):
    def test_extremes_bracket_the_endpoints(self):
        for b in (-0.01, 0.0, 0.01):
            hi, lo = bridge_extremes(b, 0.002, 0.4, 0.6)
            self.assertGreaterEqual(hi + 1e-12, max(0.0, b))
            self.assertLessEqual(lo - 1e-12, min(0.0, b))

    def test_mean_range_matches_theory(self):
        """E[range] of a driftless Brownian bridge is sqrt(8/pi) * sigma."""
        import random

        rng = random.Random(0)
        sigma = 0.01
        ranges = []
        for _ in range(20_000):
            b = rng.gauss(0.0, sigma)
            hi, lo = bridge_extremes(b, sigma, rng.random(), rng.random())
            ranges.append(hi - lo)
        expected = math.sqrt(8.0 / math.pi) * sigma
        self.assertAlmostEqual(statistics.mean(ranges) / expected, 1.0, delta=0.03)


class TestGeneratedMarket(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.market = generate_market(DEFAULT_UNIVERSE, 8640, 12, 0.8, VenueConfig())

    def test_realised_vol_is_in_the_right_ballpark(self):
        """Measured annualised vol should sit near the configured vol.

        The tolerance is wide on purpose: regime multipliers and jumps mean
        the realised number is not supposed to equal the input exactly.  The
        test is here to catch an order-of-magnitude error in the time step,
        which is the bug that silently invalidates everything downstream.
        """
        for spec in DEFAULT_UNIVERSE:
            rets = log_returns(self.market.bars[spec.symbol])
            realised = statistics.stdev(rets) * math.sqrt(BARS_PER_YEAR)
            floor = 0.35 * math.hypot(spec.beta * 0.55, spec.annual_vol)
            ceil = 1.8 * math.hypot(spec.beta * 0.55, spec.annual_vol)
            self.assertTrue(
                floor < realised < ceil,
                f"{spec.symbol}: realised {realised:.2f} outside [{floor:.2f}, {ceil:.2f}]",
            )

    def test_ohlc_is_internally_consistent(self):
        for symbol, bars in self.market.bars.items():
            for b in bars:
                self.assertGreaterEqual(b.high + 1e-9, max(b.open, b.close), symbol)
                self.assertLessEqual(b.low - 1e-9, min(b.open, b.close), symbol)
                self.assertGreater(b.low, 0.0, symbol)

    def test_intrabar_range_is_consistent_with_close_to_close_vol(self):
        """Oversized wicks are a free kill on every stop; guard against them."""
        for spec in DEFAULT_UNIVERSE:
            bars = self.market.bars[spec.symbol]
            sd = statistics.stdev(log_returns(bars))
            mean_range = statistics.mean(math.log(b.high / b.low) for b in bars)
            ratio = mean_range / (math.sqrt(8.0 / math.pi) * sd)
            self.assertTrue(
                0.75 < ratio < 1.15,
                f"{spec.symbol}: intrabar range is {ratio:.2f}x the Brownian expectation",
            )

    def test_funding_is_bounded_and_small(self):
        for symbol, rates in self.market.funding.items():
            self.assertLessEqual(max(rates), FUNDING_CAP + 1e-12, symbol)
            self.assertGreaterEqual(min(rates), -FUNDING_CAP - 1e-12, symbol)
            annualised = statistics.mean(rates) * 3 * 365
            self.assertLess(abs(annualised), 0.75, f"{symbol} funding {annualised:.2f}/yr")

    def test_determinism(self):
        """Same seed and same length reproduce the same market, exactly.

        Note the *same length* qualifier: the regime path is drawn up front,
        so a 500-bar market is not a prefix of an 8,640-bar one.  Runs are
        reproducible; they are not nested.
        """
        again = generate_market(DEFAULT_UNIVERSE, 8640, 12, 0.8, VenueConfig())
        for symbol in self.market.bars:
            self.assertEqual(
                [b.close for b in again.bars[symbol]],
                [b.close for b in self.market.bars[symbol]],
                symbol,
            )
        shorter = generate_market(DEFAULT_UNIVERSE, 500, 12, 0.8, VenueConfig())
        self.assertEqual(len(shorter.bars["BTC-PERP"]), 500)

    def test_predictability_zero_leaves_returns_unpredictable(self):
        """With the dial at zero, daily returns should show no autocorrelation."""
        flat = generate_market(DEFAULT_UNIVERSE, 20_000, 5, 0.0, VenueConfig())
        rets = log_returns(flat.bars["BTC-PERP"])
        day = 288
        daily = [sum(rets[i : i + day]) for i in range(0, len(rets) - day, day)]
        m = statistics.mean(daily)
        num = sum((a - m) * (b - m) for a, b in zip(daily, daily[1:]))
        den = sum((x - m) ** 2 for x in daily)
        self.assertLess(abs(num / den), 0.25)


class TestPredictabilityCalibration(unittest.TestCase):
    """The dial must mean what it says.

    `predictability` is defined as the annualised Sharpe a matched trend
    filter can extract before costs.  That claim is calibrated empirically,
    not derived and trusted, so it needs a test that measures it back out of
    generated data.

    The test compares against the *dial-zero baseline on the same seeds*
    rather than against zero directly.  A Sharpe estimated from a handful of
    simulated months has a standard error of order 0.5, so the absolute level
    is noisy; using common random numbers cancels most of that and makes the
    slope measurable.
    """

    SEEDS = (301, 302, 303, 304, 305, 306)

    @staticmethod
    def matched_filter_sharpe(predictability: float, seeds) -> float:
        from paper_trader.config import BARS_PER_DAY

        half_life = BARS_PER_DAY
        alpha = 1.0 - 0.5 ** (1.0 / half_life)
        pnl = []
        for seed in seeds:
            m = generate_market(DEFAULT_UNIVERSE, 30 * BARS_PER_DAY, seed,
                                predictability, VenueConfig())
            for symbol in m.symbols:
                rets = log_returns(m.bars[symbol])
                sd = statistics.stdev(rets)
                ema = 0.0
                for i in range(len(rets) - 1):
                    ema = alpha * rets[i] + (1 - alpha) * ema
                    z = ema / (sd * math.sqrt(alpha / (2 - alpha)))
                    pnl.append(max(-3.0, min(3.0, z)) * rets[i + 1] / sd)
        mean = statistics.mean(pnl)
        return mean / statistics.stdev(pnl) * math.sqrt(BARS_PER_YEAR)

    def test_dial_increases_extractable_sharpe_roughly_one_for_one(self):
        base = self.matched_filter_sharpe(0.0, self.SEEDS)
        high = self.matched_filter_sharpe(2.0, self.SEEDS)
        excess = high - base
        self.assertGreater(excess, 1.0, "the dial barely moved the achievable Sharpe")
        self.assertLess(excess, 3.5, "the dial is handing out far more edge than it claims")

    def test_dial_is_monotone(self):
        values = [self.matched_filter_sharpe(p, self.SEEDS[:4]) for p in (0.0, 1.0, 2.0)]
        self.assertEqual(values, sorted(values))


if __name__ == "__main__":
    unittest.main()
