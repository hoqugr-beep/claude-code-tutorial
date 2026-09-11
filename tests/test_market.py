"""Provider parsing tests. No network: ``_http_get`` is always mocked."""

import datetime as dt
import json
import unittest
from unittest import mock

from stockcast import market
from stockcast.errors import MarketDataError
from stockcast.market import Bar, PriceHistory, fetch_stooq, fetch_yahoo, get_history

STOOQ_CSV = (
    "Date,Open,High,Low,Close,Volume\n"
    "2026-09-08,100.0,102.0,99.0,101.5,1000\n"
    "2026-09-09,101.5,103.0,101.0,102.25,1100\n"
    "2026-09-10,102.25,104.0,102.0,103.75,1200\n"
)

YAHOO_JSON = {
    "chart": {
        "error": None,
        "result": [
            {
                "timestamp": [1757289600, 1757376000, 1757462400],
                "indicators": {
                    "quote": [
                        {
                            "open": [100.0, 101.5, None],
                            "high": [102.0, 103.0, 104.0],
                            "low": [99.0, 101.0, 102.0],
                            "close": [101.5, 102.25, None],
                            "volume": [1000, 1100, 1200],
                        }
                    ]
                },
            }
        ]
    }
}


class TestPriceHistory(unittest.TestCase):
    def _bars(self, n):
        return [
            Bar(dt.date(2026, 1, 1) + dt.timedelta(days=i), 1, 1, 1, 100.0 + i)
            for i in range(n)
        ]

    def test_needs_at_least_two_bars(self):
        with self.assertRaises(MarketDataError):
            PriceHistory("X", self._bars(1), "test")

    def test_accessors(self):
        history = PriceHistory("X", self._bars(5), "test")
        self.assertEqual(history.closes, [100.0, 101.0, 102.0, 103.0, 104.0])
        self.assertEqual(history.last.close, 104.0)
        self.assertEqual(history.start, dt.date(2026, 1, 1))
        self.assertEqual(history.tail(2).closes, [103.0, 104.0])


class TestStooq(unittest.TestCase):
    def test_parses_csv(self):
        with mock.patch.object(market, "_http_get",
                               return_value=STOOQ_CSV.encode()) as http:
            history = fetch_stooq("orcl")
        self.assertEqual(history.ticker, "ORCL")
        self.assertEqual(history.closes, [101.5, 102.25, 103.75])
        self.assertEqual(history.last.date, dt.date(2026, 9, 10))
        self.assertIn("orcl.us", http.call_args[0][0])

    def test_bars_are_sorted_oldest_first(self):
        shuffled = (
            "Date,Open,High,Low,Close,Volume\n"
            "2026-09-10,1,1,1,103.75,1\n"
            "2026-09-08,1,1,1,101.5,1\n"
            "2026-09-09,1,1,1,102.25,1\n"
        )
        with mock.patch.object(market, "_http_get", return_value=shuffled.encode()):
            self.assertEqual(fetch_stooq("X").closes, [101.5, 102.25, 103.75])

    def test_unknown_symbol_raises(self):
        with mock.patch.object(market, "_http_get", return_value=b"No data\n"):
            with self.assertRaises(MarketDataError):
                fetch_stooq("NOSUCHTICKER")

    def test_skips_rows_with_unparseable_prices(self):
        messy = STOOQ_CSV + "2026-09-11,x,x,x,N/A,0\n2026-09-12,1,1,1,105.0,1\n"
        with mock.patch.object(market, "_http_get", return_value=messy.encode()):
            self.assertEqual(len(fetch_stooq("X").bars), 4)


class TestYahoo(unittest.TestCase):
    def test_parses_json_and_drops_null_closes(self):
        payload = json.dumps(YAHOO_JSON).encode()
        with mock.patch.object(market, "_http_get", return_value=payload):
            history = fetch_yahoo("ORCL")
        # The third session has a null close and must be dropped, not zeroed.
        self.assertEqual(history.closes, [101.5, 102.25])

    def test_missing_open_falls_back_to_close(self):
        payload = json.dumps(YAHOO_JSON).encode()
        with mock.patch.object(market, "_http_get", return_value=payload):
            history = fetch_yahoo("ORCL")
        self.assertEqual(history.bars[1].open, 101.5)

    def test_api_error_raises(self):
        payload = json.dumps({"chart": {"error": {"code": "Not Found"}}}).encode()
        with mock.patch.object(market, "_http_get", return_value=payload):
            with self.assertRaises(MarketDataError):
                fetch_yahoo("NOPE")

    def test_empty_result_raises(self):
        payload = json.dumps({"chart": {"result": []}}).encode()
        with mock.patch.object(market, "_http_get", return_value=payload):
            with self.assertRaises(MarketDataError):
                fetch_yahoo("NOPE")

    def test_non_json_raises(self):
        with mock.patch.object(market, "_http_get", return_value=b"<html>502</html>"):
            with self.assertRaises(MarketDataError):
                fetch_yahoo("ORCL")


class TestProviderFallback(unittest.TestCase):
    def test_falls_through_to_the_next_provider(self):
        good = PriceHistory(
            "X",
            [Bar(dt.date(2026, 1, 1), 1, 1, 1, 10.0),
             Bar(dt.date(2026, 1, 2), 1, 1, 1, 11.0)],
            "yahoo",
        )
        with mock.patch.dict(
            market.PROVIDERS,
            {
                "stooq": mock.Mock(side_effect=MarketDataError("down")),
                "yahoo": mock.Mock(return_value=good),
            },
        ):
            history = get_history("X", providers=("stooq", "yahoo"), use_cache=False)
        self.assertEqual(history.source, "yahoo")

    def test_survives_a_provider_raising_something_unexpected(self):
        good = PriceHistory(
            "X",
            [Bar(dt.date(2026, 1, 1), 1, 1, 1, 10.0),
             Bar(dt.date(2026, 1, 2), 1, 1, 1, 11.0)],
            "yahoo",
        )
        with mock.patch.dict(
            market.PROVIDERS,
            {
                "stooq": mock.Mock(side_effect=RuntimeError("kaboom")),
                "yahoo": mock.Mock(return_value=good),
            },
        ):
            history = get_history("X", providers=("stooq", "yahoo"), use_cache=False)
        self.assertEqual(history.source, "yahoo")

    def test_total_failure_reports_every_provider(self):
        with mock.patch.dict(
            market.PROVIDERS,
            {
                "stooq": mock.Mock(side_effect=MarketDataError("stooq down")),
                "yahoo": mock.Mock(side_effect=MarketDataError("yahoo down")),
            },
        ):
            with self.assertRaises(MarketDataError) as caught:
                get_history("X", providers=("stooq", "yahoo"), use_cache=False)
        message = str(caught.exception)
        self.assertIn("stooq down", message)
        self.assertIn("yahoo down", message)

    def test_unknown_provider_name_is_reported(self):
        with self.assertRaises(MarketDataError) as caught:
            get_history("X", providers=("nonesuch",), use_cache=False)
        self.assertIn("no such provider", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
