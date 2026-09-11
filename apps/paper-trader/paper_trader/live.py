"""Real market data from public exchange REST endpoints.

Stdlib only (`urllib`), no API key, no third-party client. Three venues are
supported because availability differs by country and by network policy —
if one is unreachable for you, another usually is not.

Response shapes below were taken from each venue's published documentation,
not from memory. They are cited at each adapter. What could NOT be verified
from this machine is the endpoints actually responding: every exchange
domain tried here was refused by the network egress policy (HTTP 403 at the
proxy), so no live call has ever been executed against this code. The
parsers are tested against captured-shape fixtures in
`tests/test_live.py`; the transport is not. Run `live_trade.py --check`
from a machine with network access before trusting any of it.

One correctness detail that applies to every venue: **the most recent candle
is still forming.** Kraken documents this explicitly; it is equally true of
the others. Acting on a partial bar means acting on a high/low/close that
will still change, so the newest bar is always discarded.
"""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable

USER_AGENT = "paper-trader/1.0 (simulation; no orders placed)"
DEFAULT_TIMEOUT = 25


class LiveDataUnavailable(RuntimeError):
    """Raised when market data could not be fetched, with a usable reason."""


@dataclass(frozen=True)
class LiveBar:
    ts_ms: int
    open: float
    high: float
    low: float
    close: float
    volume_base: float

    @property
    def quote_volume(self) -> float:
        """Volume in quote currency, approximated at the bar's typical price."""
        return self.volume_base * (self.high + self.low + self.close) / 3.0


@dataclass(frozen=True)
class Venue:
    name: str
    base_url: str
    build_url: Callable[[str, str, int, int], str]
    parse: Callable[[Any, str], list[LiveBar]]
    interval_token: Callable[[int], str]
    example_symbols: tuple[str, ...]
    notes: str


# --------------------------------------------------------------------------
# Binance spot
#   GET /api/v3/klines?symbol&interval&limit   (limit default 500, max 1000)
#   Each kline is an array:
#     0 open time (ms) | 1 open | 2 high | 3 low | 4 close | 5 volume (base)
#     6 close time     | 7 quote asset volume   | 8 number of trades | ...
#   Source: Binance Spot REST API, "Kline/Candlestick data".
# --------------------------------------------------------------------------

_BINANCE_INTERVALS = {1: "1m", 3: "3m", 5: "5m", 15: "15m", 30: "30m",
                      60: "1h", 120: "2h", 240: "4h", 360: "6h", 480: "8h",
                      720: "12h", 1440: "1d"}


def _binance_interval(minutes: int) -> str:
    if minutes not in _BINANCE_INTERVALS:
        raise ValueError(f"Binance has no {minutes}-minute interval; "
                         f"pick one of {sorted(_BINANCE_INTERVALS)}")
    return _BINANCE_INTERVALS[minutes]


def _binance_url(base: str, symbol: str, minutes: int, limit: int) -> str:
    q = urllib.parse.urlencode({
        "symbol": symbol,
        "interval": _binance_interval(minutes),
        "limit": min(max(limit, 1), 1000),
    })
    return f"{base}/api/v3/klines?{q}"


def _binance_parse(payload: Any, symbol: str) -> list[LiveBar]:
    if not isinstance(payload, list):
        raise LiveDataUnavailable(
            f"Binance returned {type(payload).__name__}, not a list of klines: "
            f"{str(payload)[:200]}"
        )
    out = []
    for row in payload:
        if len(row) < 6:
            raise LiveDataUnavailable(f"Binance kline row too short: {row!r}")
        out.append(LiveBar(int(row[0]), float(row[1]), float(row[2]),
                           float(row[3]), float(row[4]), float(row[5])))
    return out


# --------------------------------------------------------------------------
# Coinbase Exchange
#   GET /products/{product_id}/candles?granularity={seconds}
#   Each bucket is [ time (seconds), low, high, open, close, volume ].
#   Source: Coinbase Exchange REST API, "Get product candles" — note the
#   unusual low/high-before-open/close ordering, which is a classic source of
#   silently transposed data.  Granularity must be one of
#   {60, 300, 900, 3600, 21600, 86400} seconds or the request is rejected.
#   Coinbase returns candles NEWEST FIRST, so they are sorted here.
# --------------------------------------------------------------------------

_COINBASE_GRANULARITIES = {1: 60, 5: 300, 15: 900, 60: 3600, 360: 21600, 1440: 86400}


def _coinbase_interval(minutes: int) -> str:
    if minutes not in _COINBASE_GRANULARITIES:
        raise ValueError(f"Coinbase only supports "
                         f"{sorted(_COINBASE_GRANULARITIES)}-minute candles")
    return str(_COINBASE_GRANULARITIES[minutes])


def _coinbase_url(base: str, symbol: str, minutes: int, limit: int) -> str:
    # Coinbase caps a response at 300 candles and has no `limit` parameter.
    q = urllib.parse.urlencode({"granularity": _coinbase_interval(minutes)})
    return f"{base}/products/{urllib.parse.quote(symbol)}/candles?{q}"


def _coinbase_parse(payload: Any, symbol: str) -> list[LiveBar]:
    if isinstance(payload, dict):
        raise LiveDataUnavailable(
            f"Coinbase returned an error for {symbol}: {payload.get('message', payload)}"
        )
    if not isinstance(payload, list):
        raise LiveDataUnavailable(f"Coinbase returned unexpected payload: {str(payload)[:200]}")
    out = []
    for row in payload:
        if len(row) < 6:
            raise LiveDataUnavailable(f"Coinbase candle row too short: {row!r}")
        ts, low, high, open_, close, vol = row[:6]
        out.append(LiveBar(int(ts) * 1000, float(open_), float(high),
                           float(low), float(close), float(vol)))
    out.sort(key=lambda b: b.ts_ms)
    return out


# --------------------------------------------------------------------------
# Kraken
#   GET /0/public/OHLC?pair={pair}&interval={minutes}
#   -> {"error": [...], "result": {"<pair>": [[time, open, high, low, close,
#                                              vwap, volume, count], ...],
#                                  "last": <id>}}
#   Source: Kraken REST API, "Get OHLC Data".  Returns up to 720 entries and
#   documents that the final entry is the current, not-yet-committed bar.
#   Kraken renames pairs in the response (XBTUSD -> XXBTZUSD), so the result
#   key is discovered rather than assumed.
# --------------------------------------------------------------------------

_KRAKEN_INTERVALS = {1, 5, 15, 30, 60, 240, 1440, 10080, 21600}


def _kraken_interval(minutes: int) -> str:
    if minutes not in _KRAKEN_INTERVALS:
        raise ValueError(f"Kraken only supports {sorted(_KRAKEN_INTERVALS)}-minute intervals")
    return str(minutes)


def _kraken_url(base: str, symbol: str, minutes: int, limit: int) -> str:
    q = urllib.parse.urlencode({"pair": symbol, "interval": _kraken_interval(minutes)})
    return f"{base}/0/public/OHLC?{q}"


def _kraken_parse(payload: Any, symbol: str) -> list[LiveBar]:
    if not isinstance(payload, dict):
        raise LiveDataUnavailable(f"Kraken returned unexpected payload: {str(payload)[:200]}")
    errors = payload.get("error") or []
    if errors:
        raise LiveDataUnavailable(f"Kraken error for {symbol}: {errors}")
    result = payload.get("result") or {}
    series = [v for k, v in result.items() if k != "last" and isinstance(v, list)]
    if not series:
        raise LiveDataUnavailable(f"Kraken returned no OHLC series for {symbol}")
    out = []
    for row in series[0]:
        if len(row) < 7:
            raise LiveDataUnavailable(f"Kraken OHLC row too short: {row!r}")
        ts, open_, high, low, close = row[0], row[1], row[2], row[3], row[4]
        volume = row[6]
        out.append(LiveBar(int(ts) * 1000, float(open_), float(high),
                           float(low), float(close), float(volume)))
    out.sort(key=lambda b: b.ts_ms)
    return out


# Most bars each venue will return in a single response. Exceeding these
# silently truncates, which for a resuming account means skipped bars.
MAX_BARS_PER_CALL = {"binance": 1000, "coinbase": 300, "kraken": 720}


VENUES: dict[str, Venue] = {
    "binance": Venue(
        name="binance",
        base_url="https://api.binance.com",
        build_url=_binance_url,
        parse=_binance_parse,
        interval_token=_binance_interval,
        example_symbols=("BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"),
        notes="Spot klines. Not available from every country.",
    ),
    "coinbase": Venue(
        name="coinbase",
        base_url="https://api.exchange.coinbase.com",
        build_url=_coinbase_url,
        parse=_coinbase_parse,
        interval_token=_coinbase_interval,
        example_symbols=("BTC-USD", "ETH-USD", "SOL-USD", "DOGE-USD"),
        notes="Coinbase Exchange candles; max 300 per response, no limit parameter.",
    ),
    "kraken": Venue(
        name="kraken",
        base_url="https://api.kraken.com",
        build_url=_kraken_url,
        parse=_kraken_parse,
        interval_token=_kraken_interval,
        example_symbols=("XBTUSD", "ETHUSD", "SOLUSD", "XDGUSD"),
        notes="Max 720 candles per call; documents that the last bar is incomplete.",
    ),
}


def http_get_json(url: str, timeout: int = DEFAULT_TIMEOUT) -> Any:
    """GET a URL and parse JSON, turning transport failures into clear errors."""
    request = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    })
    try:
        # Uses the default SSL context, which honours SSL_CERT_FILE — the
        # variable a corporate MITM proxy sets to its own CA bundle.
        with urllib.request.urlopen(request, timeout=timeout,
                                    context=ssl.create_default_context()) as resp:
            body = resp.read()
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:300]
        except Exception:
            pass
        if exc.code in (403, 407):
            raise LiveDataUnavailable(
                f"{urllib.parse.urlsplit(url).netloc} refused the request "
                f"(HTTP {exc.code}). On a managed network this is normally the "
                f"egress proxy's allowlist rather than the exchange: the host has "
                f"to be permitted before this can work. {detail}"
            ) from exc
        if exc.code == 429:
            raise LiveDataUnavailable(
                f"Rate limited by {urllib.parse.urlsplit(url).netloc} (HTTP 429). "
                f"Back off and retry later. {detail}"
            ) from exc
        raise LiveDataUnavailable(f"HTTP {exc.code} from {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise LiveDataUnavailable(
            f"Could not reach {urllib.parse.urlsplit(url).netloc}: {exc.reason}. "
            f"Check network access, proxy settings, and TLS trust."
        ) from exc
    except OSError as exc:
        raise LiveDataUnavailable(f"Network error fetching {url}: {exc}") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise LiveDataUnavailable(
            f"{urllib.parse.urlsplit(url).netloc} did not return JSON. "
            f"First 200 bytes: {body[:200]!r}"
        ) from exc


def validate_bars(bars: list[LiveBar], symbol: str) -> list[LiveBar]:
    """Reject data that cannot be right before it reaches the strategy.

    Bad market data is worse than no market data: it produces a confident
    wrong answer.  These checks are cheap and catch the common failures —
    transposed high/low (the Coinbase column order is a real trap),
    non-positive prices, duplicated or out-of-order timestamps.
    """
    clean: list[LiveBar] = []
    seen: set[int] = set()
    for b in bars:
        if min(b.open, b.high, b.low, b.close) <= 0:
            raise LiveDataUnavailable(f"{symbol}: non-positive price in bar {b}")
        if b.high < b.low:
            raise LiveDataUnavailable(
                f"{symbol}: high {b.high} below low {b.low} — the columns are "
                f"probably transposed for this venue"
            )
        if not (b.low - 1e-9 <= b.open <= b.high + 1e-9):
            raise LiveDataUnavailable(f"{symbol}: open {b.open} outside [{b.low}, {b.high}]")
        if not (b.low - 1e-9 <= b.close <= b.high + 1e-9):
            raise LiveDataUnavailable(f"{symbol}: close {b.close} outside [{b.low}, {b.high}]")
        if b.volume_base < 0:
            raise LiveDataUnavailable(f"{symbol}: negative volume in bar {b}")
        if b.ts_ms in seen:
            continue
        seen.add(b.ts_ms)
        clean.append(b)
    clean.sort(key=lambda b: b.ts_ms)
    return clean


def fetch_bars(
    venue_name: str,
    symbol: str,
    interval_minutes: int = 5,
    limit: int = 500,
    base_url: str | None = None,
    drop_forming_bar: bool = True,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[LiveBar]:
    """Fetch up to `limit` *completed* candles for one symbol, oldest first.

    The newest candle is dropped by default because it is still forming — its
    high, low and close will all still change. Venues that honour a
    server-side limit are therefore asked for one extra bar, so that `limit`
    means the same thing everywhere: the number of completed bars returned.
    """
    if venue_name not in VENUES:
        raise ValueError(f"unknown venue {venue_name!r}; have {sorted(VENUES)}")
    venue = VENUES[venue_name]
    ask = limit + 1 if drop_forming_bar else limit
    url = venue.build_url(base_url or venue.base_url, symbol, interval_minutes, ask)
    bars = validate_bars(venue.parse(http_get_json(url, timeout), symbol), symbol)
    if drop_forming_bar and bars:
        bars = bars[:-1]
    if not bars:
        raise LiveDataUnavailable(f"{venue_name} returned no usable bars for {symbol}")
    return bars[-limit:]


def check_connection(
    venue_name: str, symbol: str | None = None, base_url: str | None = None
) -> dict:
    """Try one small fetch and report what happened, without raising."""
    venue = VENUES[venue_name]
    symbol = symbol or venue.example_symbols[0]
    url = venue.build_url(base_url or venue.base_url, symbol, 5, 3)
    try:
        bars = fetch_bars(venue_name, symbol, 5, 3, base_url=base_url)
    except (LiveDataUnavailable, ValueError) as exc:
        return {"venue": venue_name, "symbol": symbol, "url": url,
                "ok": False, "error": str(exc)}
    return {"venue": venue_name, "symbol": symbol, "url": url, "ok": True,
            "bars": len(bars), "latest_close": bars[-1].close,
            "latest_ts_ms": bars[-1].ts_ms}


# --------------------------------------------------------------------------
# Adapting live bars to the Market interface the agent already speaks
# --------------------------------------------------------------------------

def build_live_market(
    series: dict[str, list[LiveBar]],
    interval_minutes: int = 5,
    funding_rate: float = 0.0,
):
    """Turn fetched candles into the `Market` object the agent consumes.

    Two honest limitations are baked in here:

    * **Funding is zero by default.** These are spot candles; spot markets
      have no funding rate. The account still simulates a leveraged
      perpetual on top of real spot prices, so leverage, margin and
      liquidation are modelled while the funding cost of holding that
      leverage is not. Pass `funding_rate` if you want to charge a flat one.
    * **Average daily volume is measured from the fetched bars**, so the
      market-impact model is driven by real turnover rather than a guess —
      but only over the window fetched.

    Symbols are aligned on timestamps present in *every* series; a bar
    missing for one symbol is dropped for all of them, so the agent never
    sees two symbols at different points in time.
    """
    from .config import AssetSpec
    from .market import Bar, Market

    if not series:
        raise LiveDataUnavailable("no series to build a market from")

    common = set.intersection(*({b.ts_ms for b in bars} for bars in series.values()))
    if not common:
        raise LiveDataUnavailable(
            "the fetched symbols share no common timestamps — they cannot be "
            "traded as one portfolio"
        )
    stamps = sorted(common)

    bars_per_day = (24 * 60) // interval_minutes
    assets: list[AssetSpec] = []
    out_bars: dict[str, list[Bar]] = {}
    funding: dict[str, list[float]] = {}

    for symbol, raw in series.items():
        by_ts = {b.ts_ms: b for b in raw}
        picked = [by_ts[t] for t in stamps]
        mean_quote = sum(b.quote_volume for b in picked) / len(picked)
        adv = max(mean_quote * bars_per_day, 1.0)
        out_bars[symbol] = [
            Bar(i, b.open, b.high, b.low, b.close, b.quote_volume)
            for i, b in enumerate(picked)
        ]
        funding[symbol] = [funding_rate] * len(picked)
        assets.append(AssetSpec(
            symbol=symbol,
            start_price=picked[0].open,
            annual_drift=0.0,
            annual_vol=0.0,
            beta=1.0,
            jump_per_year=0.0,
            jump_vol=0.0,
            adv_usd=adv,
        ))

    market = Market(tuple(assets), out_bars, ["live"] * len(stamps), funding)
    market.timestamps = stamps
    return market
