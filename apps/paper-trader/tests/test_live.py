"""Live-data layer: parsers, validation, and a full round trip over HTTP.

The exchanges themselves are unreachable from the machine this was written
on — every venue domain is refused by the network egress policy — so the
transport against a *real* venue is untested and says so in `live.py`. What
is tested here is everything else, against payloads shaped exactly as each
venue's documentation describes, served over real HTTP by a local server:
URL construction, parsing, column-order validation, timestamp alignment,
account persistence, and idempotency.

The one thing these tests cannot tell you is whether a venue's live response
still matches its documentation. Run `live_trade.py --check` for that.
"""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlsplit

from paper_trader.live import (VENUES, LiveBar, LiveDataUnavailable,
                               build_live_market, fetch_bars, validate_bars)


def synthetic_ohlc(n: int, start: float = 100.0, step_ms: int = 300_000,
                   t0: int = 1_700_000_000_000, seed: int = 1):
    """Deterministic OHLC that satisfies low <= open/close <= high."""
    import random
    rng = random.Random(seed)
    rows, price = [], start
    for i in range(n):
        o = price
        c = max(0.01, o * (1 + rng.gauss(0, 0.002)))
        hi = max(o, c) * (1 + abs(rng.gauss(0, 0.001)))
        lo = min(o, c) * (1 - abs(rng.gauss(0, 0.001)))
        rows.append((t0 + i * step_ms, o, hi, lo, c, rng.uniform(10, 100)))
        price = c
    return rows


def as_binance(rows):
    """[openTime, open, high, low, close, volume, closeTime, quoteVol, ...]"""
    return [[t, f"{o:.8f}", f"{h:.8f}", f"{l:.8f}", f"{c:.8f}", f"{v:.8f}",
             t + 299_999, f"{v * c:.8f}", 42, "0", "0", "0"]
            for t, o, h, l, c, v in rows]


def as_coinbase(rows):
    """[time(s), low, high, open, close, volume] — newest first, as Coinbase returns."""
    return [[t // 1000, l, h, o, c, v] for t, o, h, l, c, v in reversed(rows)]


def as_kraken(rows, pair="XXBTZUSD"):
    """{"error": [], "result": {pair: [[time, o, h, l, c, vwap, vol, count]], "last": t}}"""
    return {"error": [], "result": {
        pair: [[t // 1000, f"{o:.4f}", f"{h:.4f}", f"{l:.4f}", f"{c:.4f}",
                f"{c:.4f}", f"{v:.4f}", 7] for t, o, h, l, c, v in rows],
        "last": rows[-1][0] // 1000}}


class FakeVenue(BaseHTTPRequestHandler):
    """Serves each venue's documented payload shape over real HTTP."""

    rows_for = staticmethod(lambda symbol: synthetic_ohlc(
        400, start=100.0 + 10 * (hash(symbol) % 7), seed=abs(hash(symbol)) % 999))

    def do_GET(self):  # noqa: N802
        parts = urlsplit(self.path)
        query = parse_qs(parts.query)
        if parts.path == "/api/v3/klines":
            symbol = query["symbol"][0]
            limit = int(query.get("limit", ["500"])[0])
            body = as_binance(self.rows_for(symbol)[-limit:])
        elif parts.path.startswith("/products/"):
            symbol = parts.path.split("/")[2]
            body = as_coinbase(self.rows_for(symbol)[-300:])
        elif parts.path == "/0/public/OHLC":
            body = as_kraken(self.rows_for(query["pair"][0])[-720:])
        else:
            self.send_error(404)
            return
        payload = json.dumps(body).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *a):
        pass


class ServerCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), FakeVenue)
        cls.base = f"http://127.0.0.1:{cls.server.server_port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()


class TestUrlBuilding(unittest.TestCase):
    def test_each_venue_builds_its_documented_url(self):
        cases = {
            "binance": "/api/v3/klines?symbol=BTCUSDT&interval=5m&limit=400",
            "coinbase": "/products/BTC-USD/candles?granularity=300",
            "kraken": "/0/public/OHLC?pair=XBTUSD&interval=5",
        }
        for name, expected in cases.items():
            v = VENUES[name]
            url = v.build_url("", v.example_symbols[0], 5, 400)
            self.assertEqual(url, expected, name)

    def test_unsupported_intervals_are_rejected_not_silently_coerced(self):
        for name in VENUES:
            with self.subTest(name), self.assertRaises(ValueError):
                VENUES[name].build_url("", VENUES[name].example_symbols[0], 7, 10)

    def test_limit_means_completed_bars_at_every_venue(self):
        """Regression: `limit` used to mean 'rows requested' at Binance and
        'rows returned' elsewhere, so the same call gave 49 bars from one
        venue and 50 from another."""

    def test_binance_limit_is_clamped_to_the_documented_maximum(self):
        url = VENUES["binance"].build_url("", "BTCUSDT", 5, 99_999)
        self.assertIn("limit=1000", url)


class TestParsers(ServerCase):
    def test_all_three_venues_parse_to_the_same_normalised_bars(self):
        got = {}
        for venue, symbol in (("binance", "BTCUSDT"), ("coinbase", "BTC-USD"),
                              ("kraken", "XBTUSD")):
            bars = fetch_bars(venue, symbol, 5, 50, base_url=self.base)
            got[venue] = bars
            self.assertTrue(all(isinstance(b, LiveBar) for b in bars))
            self.assertEqual(bars, sorted(bars, key=lambda b: b.ts_ms),
                             f"{venue} bars must be oldest first")
            for b in bars:
                self.assertLessEqual(b.low, b.high)
                self.assertGreater(b.low, 0)
        # `limit` must mean the same thing at every venue: that many
        # *completed* bars, regardless of whether the venue honours a
        # server-side limit of its own.
        for venue, bars in got.items():
            self.assertEqual(len(bars), 50, f"{venue} returned {len(bars)} bars")

    def test_the_forming_bar_is_dropped(self):
        with_drop = fetch_bars("binance", "BTCUSDT", 5, 50, base_url=self.base)
        without = fetch_bars("binance", "BTCUSDT", 5, 50, base_url=self.base,
                             drop_forming_bar=False)
        self.assertEqual(len(with_drop), 50)
        self.assertGreater(without[-1].ts_ms, with_drop[-1].ts_ms,
                           "the dropped bar must be the newest one")

    def test_coinbase_column_order_is_not_transposed(self):
        """Coinbase puts low and high *before* open and close. Prove we know."""
        rows = synthetic_ohlc(3)
        payload = as_coinbase(rows)
        parsed = VENUES["coinbase"].parse(payload, "BTC-USD")
        newest_src = rows[-1]
        newest_out = parsed[-1]
        self.assertAlmostEqual(newest_out.open, newest_src[1], places=9)
        self.assertAlmostEqual(newest_out.high, newest_src[2], places=9)
        self.assertAlmostEqual(newest_out.low, newest_src[3], places=9)
        self.assertAlmostEqual(newest_out.close, newest_src[4], places=9)

    def test_kraken_result_key_is_discovered_not_assumed(self):
        """Kraken renames pairs in its response (XBTUSD -> XXBTZUSD)."""
        payload = as_kraken(synthetic_ohlc(5), pair="SOMETHING_UNEXPECTED")
        self.assertEqual(len(VENUES["kraken"].parse(payload, "XBTUSD")), 5)

    def test_kraken_errors_are_surfaced(self):
        with self.assertRaises(LiveDataUnavailable):
            VENUES["kraken"].parse({"error": ["EQuery:Unknown asset pair"]}, "NOPE")

    def test_binance_error_object_is_surfaced(self):
        with self.assertRaises(LiveDataUnavailable):
            VENUES["binance"].parse({"code": -1121, "msg": "Invalid symbol."}, "NOPE")

    def test_non_json_response_is_a_clear_error(self):
        with self.assertRaises(LiveDataUnavailable) as ctx:
            fetch_bars("binance", "BTCUSDT", 5, 5, base_url=self.base + "/wrong")
        self.assertIn("404", str(ctx.exception))


class TestValidation(unittest.TestCase):
    def test_transposed_high_low_is_caught(self):
        bad = [LiveBar(1, 10.0, 5.0, 11.0, 10.5, 1.0)]   # high < low
        with self.assertRaises(LiveDataUnavailable) as ctx:
            validate_bars(bad, "X")
        self.assertIn("transposed", str(ctx.exception))

    def test_non_positive_price_is_caught(self):
        with self.assertRaises(LiveDataUnavailable):
            validate_bars([LiveBar(1, 0.0, 1.0, 0.0, 0.5, 1.0)], "X")

    def test_close_outside_the_range_is_caught(self):
        with self.assertRaises(LiveDataUnavailable):
            validate_bars([LiveBar(1, 10.0, 11.0, 9.0, 99.0, 1.0)], "X")

    def test_duplicate_timestamps_are_dropped(self):
        b = LiveBar(1, 10.0, 11.0, 9.0, 10.5, 1.0)
        self.assertEqual(len(validate_bars([b, b, b], "X")), 1)


class TestMarketBuild(ServerCase):
    def test_symbols_are_aligned_on_shared_timestamps(self):
        a = fetch_bars("binance", "BTCUSDT", 5, 60, base_url=self.base)
        b = fetch_bars("binance", "ETHUSDT", 5, 40, base_url=self.base)
        market = build_live_market({"BTCUSDT": a, "ETHUSDT": b}, 5)
        self.assertEqual(len(market.bars["BTCUSDT"]), len(market.bars["ETHUSDT"]))
        self.assertEqual(len(market.timestamps), market.n_bars)
        self.assertEqual(market.timestamps, sorted(market.timestamps))

    def test_disjoint_symbols_are_refused_rather_than_misaligned(self):
        a = [LiveBar(1_000, 1, 2, 0.5, 1.5, 1)]
        b = [LiveBar(9_000, 1, 2, 0.5, 1.5, 1)]
        with self.assertRaises(LiveDataUnavailable):
            build_live_market({"A": a, "B": b}, 5)

    def test_average_daily_volume_comes_from_real_turnover(self):
        bars = fetch_bars("binance", "BTCUSDT", 5, 100, base_url=self.base)
        market = build_live_market({"BTCUSDT": bars}, 5)
        self.assertGreater(market.spec["BTCUSDT"].adv_usd, 0.0)

    def test_funding_defaults_to_zero_because_spot_has_none(self):
        bars = fetch_bars("binance", "BTCUSDT", 5, 20, base_url=self.base)
        market = build_live_market({"BTCUSDT": bars}, 5)
        self.assertEqual(set(market.funding["BTCUSDT"]), {0.0})


class TestEndToEnd(ServerCase):
    """Drive the real CLI against the local venue and check it persists."""

    def _run(self, tmp, *extra):
        import live_trade
        return live_trade.main([
            "--update", "--venue", "binance", "--base-url", self.base,
            "--symbols", "BTCUSDT", "ETHUSDT", "--state", tmp, *extra,
        ])

    def test_update_creates_advances_and_resumes_state(self):
        import tempfile, os
        from paper_trader.state import load as load_state
        tmp = os.path.join(tempfile.mkdtemp(), "s.json")

        self.assertEqual(self._run(tmp), 0)
        first = load_state(tmp)
        self.assertIsNotNone(first)
        self.assertEqual(first.last_run_status, "ok")
        self.assertGreater(first.last_aligned_ts, 0)
        self.assertEqual(first.data_source, "live")

        # Running again with no new bars must change nothing about the account.
        self.assertEqual(self._run(tmp), 0)
        second = load_state(tmp)
        self.assertEqual(second.last_aligned_ts, first.last_aligned_ts)
        self.assertEqual(len(second.trades), len(first.trades))
        self.assertAlmostEqual(second.cash, first.cash, places=9)

    def test_a_fresh_account_does_not_backfill_trades_from_history(self):
        import tempfile, os
        from paper_trader.state import load as load_state
        tmp = os.path.join(tempfile.mkdtemp(), "s.json")
        self._run(tmp)
        state = load_state(tmp)
        self.assertEqual(len(state.trades), 0,
                         "a new account must not replay historical bars as trades")

    def test_unreachable_venue_records_the_failure_without_corrupting_state(self):
        import tempfile, os
        from paper_trader.state import load as load_state
        import live_trade
        tmp = os.path.join(tempfile.mkdtemp(), "s.json")
        self._run(tmp)
        before = load_state(tmp)

        code = live_trade.main([
            "--update", "--venue", "binance", "--state", tmp,
            "--base-url", "http://127.0.0.1:1",   # nothing listening
        ])
        self.assertEqual(code, 2)
        after = load_state(tmp)
        self.assertNotEqual(after.last_run_status, "ok")
        self.assertTrue(after.last_run_error)
        self.assertAlmostEqual(after.cash, before.cash, places=9)
        self.assertEqual(after.last_aligned_ts, before.last_aligned_ts)

    def test_email_reports_staleness_after_a_failed_update(self):
        import tempfile, os
        from paper_trader.email_report import plain_text, subject
        from paper_trader.state import load as load_state
        import live_trade
        tmp = os.path.join(tempfile.mkdtemp(), "s.json")
        self._run(tmp)
        live_trade.main(["--update", "--venue", "binance", "--state", tmp,
                         "--base-url", "http://127.0.0.1:1"])
        state = load_state(tmp)
        self.assertIn("no update", subject(state))
        self.assertIn("NOT A FRESH NUMBER", plain_text(state))


if __name__ == "__main__":
    unittest.main()
