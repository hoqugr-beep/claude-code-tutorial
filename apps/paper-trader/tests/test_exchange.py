"""Invariants of the margin engine.

The central one: realised P&L must equal the change in account equity.  A
backtest whose ledger does not tie out can report any number it likes.
"""

import unittest

from paper_trader.config import VenueConfig
from paper_trader.exchange import Account

ADV = 1e9


def fresh(cash=1_000.0, **kw) -> Account:
    return Account(cash=cash, venue=VenueConfig(**kw))


class TestFills(unittest.TestCase):
    def test_taker_pays_up_and_sells_down(self):
        a = fresh()
        self.assertGreater(a.fill_price(100.0, 1, 1_000.0, ADV), 100.0)
        self.assertLess(a.fill_price(100.0, -1, 1_000.0, ADV), 100.0)

    def test_impact_grows_with_size(self):
        a = fresh()
        small = a.fill_price(100.0, 1, 1_000.0, ADV)
        large = a.fill_price(100.0, 1, 100_000_000.0, ADV)
        self.assertGreater(large, small)

    def test_zero_cost_venue_fills_at_mark(self):
        a = fresh(taker_fee=0.0, base_spread=0.0, impact_coef=0.0)
        self.assertAlmostEqual(a.fill_price(100.0, 1, 5_000.0, ADV), 100.0)


class TestOpenAndClose(unittest.TestCase):
    def test_open_costs_exactly_the_fee_in_equity(self):
        a = fresh(base_spread=0.0, impact_coef=0.0)
        before = a.equity({"X": 100.0})
        pos = a.open_position("X", 1, 10.0, 100.0, 0, 90.0, 160.0, 5.0, ADV)
        assert pos is not None
        after = a.equity({"X": pos.entry_price})
        self.assertAlmostEqual(before - after, pos.fees_paid, places=9)

    def test_margin_matches_leverage(self):
        a = fresh()
        pos = a.open_position("X", 1, 10.0, 100.0, 0, 90.0, 160.0, 5.0, ADV)
        assert pos is not None
        self.assertAlmostEqual(pos.margin, pos.qty * pos.entry_price / 5.0, places=9)

    def test_round_trip_at_a_flat_price_loses_only_costs(self):
        a = fresh(base_spread=0.0, impact_coef=0.0)
        start = a.equity({"X": 100.0})
        a.open_position("X", 1, 10.0, 100.0, 0, 90.0, 160.0, 5.0, ADV)
        t = a.close_position("X", 100.0, 10, "test", ADV)
        self.assertAlmostEqual(a.cash, start - t.fees, places=9)
        self.assertAlmostEqual(t.net_pnl, -t.fees, places=9)

    def test_pnl_equals_equity_change_long_and_short(self):
        for side, exit_price in ((1, 120.0), (-1, 80.0), (1, 95.0), (-1, 105.0)):
            with self.subTest(side=side, exit=exit_price):
                a = fresh()
                start = a.equity({"X": 100.0})
                a.open_position("X", side, 10.0, 100.0, 0, 100.0 - side * 10, 0.0, 5.0, ADV)
                t = a.close_position("X", exit_price, 10, "test", ADV)
                self.assertAlmostEqual(a.equity({}) - start, t.net_pnl, places=9)

    def test_venue_rejects_orders_it_cannot_margin(self):
        a = fresh(cash=10.0)
        self.assertIsNone(a.open_position("X", 1, 100.0, 100.0, 0, 90.0, 0.0, 2.0, ADV))
        self.assertEqual(a.rejected_orders, 1)

    def test_venue_rejects_dust(self):
        a = fresh()
        self.assertIsNone(a.open_position("X", 1, 0.01, 100.0, 0, 90.0, 0.0, 5.0, ADV))

    def test_leverage_capped_at_venue_maximum(self):
        a = fresh(max_leverage=10.0)
        pos = a.open_position("X", 1, 5.0, 100.0, 0, 90.0, 0.0, 500.0, ADV)
        assert pos is not None
        self.assertEqual(pos.leverage, 10.0)


class TestPyramiding(unittest.TestCase):
    def test_average_entry_and_margin_accumulate(self):
        a = fresh(taker_fee=0.0, base_spread=0.0, impact_coef=0.0)
        a.open_position("X", 1, 10.0, 100.0, 0, 90.0, 0.0, 5.0, ADV)
        self.assertTrue(a.add_to_position("X", 10.0, 110.0, ADV))
        pos = a.positions["X"]
        self.assertAlmostEqual(pos.entry_price, 105.0, places=9)
        self.assertAlmostEqual(pos.qty, 20.0, places=9)
        self.assertAlmostEqual(pos.margin, 20.0 * 105.0 / 5.0, places=9)

    def test_pnl_still_ties_out_after_pyramiding(self):
        a = fresh()
        start = a.equity({"X": 100.0})
        a.open_position("X", 1, 10.0, 100.0, 0, 90.0, 0.0, 5.0, ADV)
        a.add_to_position("X", 5.0, 110.0, ADV)
        t = a.close_position("X", 115.0, 20, "test", ADV)
        self.assertAlmostEqual(a.equity({}) - start, t.net_pnl, places=9)


class TestPartialClose(unittest.TestCase):
    def test_reduce_keeps_leverage_and_liquidation_price(self):
        a = fresh()
        pos = a.open_position("X", 1, 10.0, 100.0, 0, 90.0, 0.0, 5.0, ADV)
        assert pos is not None
        mm = a.venue.maintenance_margin
        before = pos.liquidation_price(mm)
        a.reduce_position("X", 4.0, 100.0, 5, ADV)
        self.assertAlmostEqual(a.positions["X"].qty, 6.0, places=9)
        self.assertAlmostEqual(a.positions["X"].liquidation_price(mm), before, places=6)

    def test_partial_then_full_close_ties_out(self):
        """Every dollar realised must appear in the trade log, partials included."""
        a = fresh()
        start = a.equity({"X": 100.0})
        a.open_position("X", 1, 10.0, 100.0, 0, 90.0, 0.0, 5.0, ADV)
        a.reduce_position("X", 4.0, 108.0, 5, ADV)
        a.close_position("X", 112.0, 10, "test", ADV)
        realised = sum(t.net_pnl for t in a.trades)
        self.assertEqual(len(a.trades), 2)
        self.assertAlmostEqual(a.equity({}) - start, realised, places=9)

    def test_reducing_everything_closes_the_position(self):
        a = fresh()
        a.open_position("X", 1, 10.0, 100.0, 0, 90.0, 0.0, 5.0, ADV)
        a.reduce_position("X", 10.0, 105.0, 5, ADV)
        self.assertNotIn("X", a.positions)

    def test_dust_reduction_is_a_no_op(self):
        a = fresh()
        a.open_position("X", 1, 10.0, 100.0, 0, 90.0, 0.0, 5.0, ADV)
        self.assertEqual(a.reduce_position("X", 0.0001, 100.0, 5, ADV), 0.0)
        self.assertAlmostEqual(a.positions["X"].qty, 10.0, places=9)


class TestLiquidation(unittest.TestCase):
    def test_liquidation_price_is_where_equity_meets_maintenance(self):
        for side in (1, -1):
            with self.subTest(side=side):
                a = fresh()
                pos = a.open_position("X", side, 10.0, 100.0, 0, 0.0, 0.0, 10.0, ADV)
                assert pos is not None
                mm = a.venue.maintenance_margin
                lp = pos.liquidation_price(mm)
                self.assertAlmostEqual(pos.equity(lp), pos.notional(lp) * mm, places=6)

    def test_higher_leverage_liquidates_sooner(self):
        a = fresh()
        low = a.open_position("A", 1, 1.0, 100.0, 0, 0.0, 0.0, 2.0, ADV)
        high = a.open_position("B", 1, 1.0, 100.0, 0, 0.0, 0.0, 20.0, ADV)
        mm = a.venue.maintenance_margin
        self.assertGreater(high.liquidation_price(mm), low.liquidation_price(mm))

    def test_liquidation_never_returns_more_than_the_margin_posted(self):
        a = fresh()
        start = a.cash
        pos = a.open_position("X", 1, 10.0, 100.0, 0, 0.0, 0.0, 10.0, ADV)
        assert pos is not None
        t = a.liquidate("X", pos.liquidation_price(a.venue.maintenance_margin), 5)
        self.assertGreaterEqual(a.cash, 0.0)
        self.assertLess(a.cash, start)
        self.assertLess(t.net_pnl, 0.0)
        self.assertAlmostEqual(a.equity({}) - start, t.net_pnl, places=9)

    def test_account_cannot_go_negative_on_a_gap(self):
        a = fresh()
        a.open_position("X", 1, 10.0, 100.0, 0, 0.0, 0.0, 20.0, ADV)
        a.close_position("X", 1.0, 5, "catastrophic gap", ADV)
        self.assertGreaterEqual(a.cash, 0.0)
        self.assertGreaterEqual(a.equity({}), 0.0)


class TestFunding(unittest.TestCase):
    def test_longs_pay_when_funding_is_positive(self):
        a = fresh()
        pos = a.open_position("X", 1, 10.0, 100.0, 0, 90.0, 0.0, 5.0, ADV)
        assert pos is not None
        before = pos.margin
        paid = a.settle_funding({"X": 0.001}, {"X": 100.0})
        self.assertGreater(paid, 0.0)
        self.assertLess(pos.margin, before)

    def test_shorts_receive_when_funding_is_positive(self):
        a = fresh()
        pos = a.open_position("X", -1, 10.0, 100.0, 0, 110.0, 0.0, 5.0, ADV)
        assert pos is not None
        before = pos.margin
        self.assertLess(a.settle_funding({"X": 0.001}, {"X": 100.0}), 0.0)
        self.assertGreater(pos.margin, before)

    def test_funding_moves_the_liquidation_price_against_the_payer(self):
        a = fresh()
        pos = a.open_position("X", 1, 10.0, 100.0, 0, 90.0, 0.0, 10.0, ADV)
        assert pos is not None
        mm = a.venue.maintenance_margin
        before = pos.liquidation_price(mm)
        a.settle_funding({"X": 0.002}, {"X": 100.0})
        self.assertGreater(pos.liquidation_price(mm), before)

    def test_funding_is_included_in_realised_pnl(self):
        a = fresh()
        start = a.equity({"X": 100.0})
        a.open_position("X", 1, 10.0, 100.0, 0, 90.0, 0.0, 5.0, ADV)
        a.settle_funding({"X": 0.002}, {"X": 100.0})
        t = a.close_position("X", 100.0, 10, "test", ADV)
        self.assertGreater(t.funding, 0.0)
        self.assertAlmostEqual(a.equity({}) - start, t.net_pnl, places=9)


if __name__ == "__main__":
    unittest.main()
