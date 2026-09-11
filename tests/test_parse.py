import datetime as dt
import unittest

from stockcast.errors import ParseError
from stockcast.parse import parse_request

FRIDAY = dt.date(2026, 9, 11)


class TestParseRequest(unittest.TestCase):
    def test_the_headline_example(self):
        q = parse_request("ORCL 1 week from today", FRIDAY)
        self.assertEqual(q.ticker, "ORCL")
        self.assertEqual(q.target_date, dt.date(2026, 9, 18))
        self.assertEqual(q.trading_days, 5)
        self.assertEqual(q.horizon_label, "1 week")

    def test_equivalent_spellings_agree(self):
        forms = ["ORCL 1 week", "ORCL 1w", "orcl one week from today", "ORCL 7 days"]
        targets = {parse_request(f, FRIDAY).target_date for f in forms}
        self.assertEqual(targets, {dt.date(2026, 9, 18)})

    def test_case_and_dollar_sign(self):
        self.assertEqual(parse_request("$aapl 3 days", FRIDAY).ticker, "AAPL")

    def test_class_share_ticker(self):
        self.assertEqual(parse_request("BRK.B 1 month", FRIDAY).ticker, "BRK.B")

    def test_explicit_iso_date(self):
        q = parse_request("NVDA 2026-12-31", FRIDAY)
        self.assertEqual(q.target_date, dt.date(2026, 12, 31))

    def test_months_and_years(self):
        self.assertEqual(
            parse_request("MSFT 2 months", FRIDAY).target_date, dt.date(2026, 11, 10)
        )
        self.assertEqual(
            parse_request("MSFT 1 year", FRIDAY).target_date, dt.date(2027, 9, 13)
        )

    def test_weekend_target_rolls_to_next_session(self):
        q = parse_request("TSLA tomorrow", FRIDAY)  # Saturday
        self.assertEqual(q.rolled_from, dt.date(2026, 9, 12))
        self.assertEqual(q.target_date, dt.date(2026, 9, 14))  # Monday
        self.assertGreaterEqual(q.trading_days, 1)

    def test_target_is_always_a_session_with_at_least_one_day(self):
        for horizon in ("tomorrow", "1 day", "2 days", "3 days", "1 week"):
            q = parse_request(f"ORCL {horizon}", FRIDAY)
            self.assertGreaterEqual(
                q.trading_days, 1, f"{horizon} produced a zero-length horizon"
            )

    def test_rejects_missing_timeframe(self):
        with self.assertRaises(ParseError):
            parse_request("ORCL", FRIDAY)

    def test_rejects_unparseable_timeframe(self):
        with self.assertRaises(ParseError):
            parse_request("ORCL 5 fortnights", FRIDAY)

    def test_rejects_past_date(self):
        with self.assertRaises(ParseError):
            parse_request("ORCL 2020-01-01", FRIDAY)

    def test_rejects_empty(self):
        with self.assertRaises(ParseError):
            parse_request("   ", FRIDAY)

    def test_rejects_horizon_beyond_two_years(self):
        with self.assertRaises(ParseError):
            parse_request("ORCL 5 years", FRIDAY)

    def test_rejects_zero_and_negative(self):
        with self.assertRaises(ParseError):
            parse_request("ORCL 0 days", FRIDAY)


if __name__ == "__main__":
    unittest.main()
