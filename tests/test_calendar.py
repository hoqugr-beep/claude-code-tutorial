import datetime as dt
import unittest

from stockcast.calendar_us import (
    easter_sunday,
    is_trading_day,
    market_holidays,
    trading_days_between,
)


class TestEaster(unittest.TestCase):
    def test_known_dates(self):
        for year, expected in [
            (2024, dt.date(2024, 3, 31)),
            (2025, dt.date(2025, 4, 20)),
            (2026, dt.date(2026, 4, 5)),
            (2027, dt.date(2027, 3, 28)),
        ]:
            self.assertEqual(easter_sunday(year), expected, year)

    def test_always_a_sunday(self):
        for year in range(1900, 2100):
            self.assertEqual(easter_sunday(year).weekday(), 6, year)

    def test_falls_in_march_or_april(self):
        for year in range(1900, 2100):
            self.assertIn(easter_sunday(year).month, (3, 4), year)


class TestHolidays(unittest.TestCase):
    def test_2026_schedule(self):
        holidays = market_holidays(2026)
        # July 4th 2026 is a Saturday, so observed on Friday the 3rd.
        self.assertIn(dt.date(2026, 7, 3), holidays)
        self.assertNotIn(dt.date(2026, 7, 4), holidays)
        self.assertIn(dt.date(2026, 12, 25), holidays)   # Christmas, a Friday
        self.assertIn(dt.date(2026, 11, 26), holidays)   # 4th Thursday
        self.assertIn(dt.date(2026, 9, 7), holidays)     # Labor Day
        self.assertIn(dt.date(2026, 4, 3), holidays)     # Good Friday

    def test_no_holiday_lands_on_a_weekend(self):
        for year in range(2020, 2035):
            for day in market_holidays(year):
                self.assertLess(day.weekday(), 5, f"{day} is a weekend")

    def test_juneteenth_only_from_2022(self):
        self.assertNotIn(dt.date(2021, 6, 18), market_holidays(2021))
        self.assertIn(dt.date(2022, 6, 20), market_holidays(2022))  # Sun -> Mon

    def test_nine_or_ten_holidays_per_year(self):
        for year in range(2015, 2035):
            expected = 10 if year >= 2022 else 9
            self.assertEqual(len(market_holidays(year)), expected, year)


class TestTradingDays(unittest.TestCase):
    def test_weekend_is_closed(self):
        self.assertFalse(is_trading_day(dt.date(2026, 9, 12)))  # Saturday
        self.assertTrue(is_trading_day(dt.date(2026, 9, 11)))   # Friday

    def test_one_week_is_five_sessions(self):
        self.assertEqual(
            trading_days_between(dt.date(2026, 9, 11), dt.date(2026, 9, 18)), 5
        )

    def test_holiday_week_is_short(self):
        # Thanksgiving week 2026: Thursday the 26th is closed.
        self.assertEqual(
            trading_days_between(dt.date(2026, 11, 20), dt.date(2026, 11, 27)), 4
        )

    def test_excludes_start_includes_end(self):
        self.assertEqual(
            trading_days_between(dt.date(2026, 9, 11), dt.date(2026, 9, 14)), 1
        )

    def test_non_positive_span(self):
        day = dt.date(2026, 9, 11)
        self.assertEqual(trading_days_between(day, day), 0)
        self.assertEqual(trading_days_between(day, day - dt.timedelta(days=5)), 0)

    def test_year_is_about_252_sessions(self):
        count = trading_days_between(dt.date(2026, 1, 1), dt.date(2026, 12, 31))
        self.assertGreaterEqual(count, 248)
        self.assertLessEqual(count, 254)


if __name__ == "__main__":
    unittest.main()
