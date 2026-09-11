"""Keyless market price history, behind a small provider interface.

No API key is required. Two providers ship by default and are tried in
order; adding another means writing one ``fetch`` function and registering
it. Every provider returns the same normalised ``PriceHistory``.

Providers here are free, unofficial endpoints. They are not covered by any
service agreement and can change or rate-limit without notice — if one
breaks, that is expected, and the next provider in the chain takes over.
"""

from __future__ import annotations

import csv
import datetime as _dt
import io
import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

from .errors import MarketDataError

__all__ = [
    "Bar",
    "PriceHistory",
    "get_history",
    "PROVIDERS",
    "fetch_stooq",
    "fetch_yahoo",
    "fetch_yfinance",
]

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
_TIMEOUT = 20
_CACHE_TTL = 60 * 30  # half an hour; daily bars do not change intraday


@dataclass(frozen=True)
class Bar:
    """One daily OHLC bar."""

    date: _dt.date
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


@dataclass(frozen=True)
class PriceHistory:
    """Daily closes for one symbol, oldest first."""

    ticker: str
    bars: Sequence[Bar]
    source: str

    def __post_init__(self) -> None:
        if len(self.bars) < 2:
            raise MarketDataError(
                f"Only {len(self.bars)} price bar(s) for {self.ticker}; "
                "at least 2 are needed to measure a return."
            )

    @property
    def closes(self) -> list[float]:
        return [b.close for b in self.bars]

    @property
    def last(self) -> Bar:
        return self.bars[-1]

    @property
    def start(self) -> _dt.date:
        return self.bars[0].date

    def tail(self, n: int) -> "PriceHistory":
        """The most recent ``n`` bars."""
        return PriceHistory(self.ticker, list(self.bars[-n:]), self.source)


# --------------------------------------------------------------------------
# HTTP helper
# --------------------------------------------------------------------------

def _http_get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise MarketDataError(f"HTTP {exc.code} from {url}") from exc
    except urllib.error.URLError as exc:
        raise MarketDataError(f"Could not reach {url}: {exc.reason}") from exc
    except TimeoutError as exc:
        raise MarketDataError(f"Timed out after {_TIMEOUT}s fetching {url}") from exc


def _as_float(value: str) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number else None  # filter NaN


# --------------------------------------------------------------------------
# Providers
# --------------------------------------------------------------------------

def fetch_stooq(ticker: str) -> PriceHistory:
    """Daily history from Stooq's public CSV endpoint. No key, no signup."""
    symbol = ticker.lower().replace(".", "-")
    if "." not in ticker and not symbol.endswith(".us"):
        symbol = f"{symbol}.us"
    url = f"https://stooq.com/q/d/l/?s={symbol}&i=d"
    payload = _http_get(url).decode("utf-8", errors="replace")

    if "Date" not in payload.split("\n", 1)[0]:
        raise MarketDataError(
            f"Stooq returned no data for {ticker!r} (unknown symbol, or the "
            "endpoint is rate-limiting)."
        )

    bars: list[Bar] = []
    for row in csv.DictReader(io.StringIO(payload)):
        close = _as_float(row.get("Close", ""))
        if close is None:
            continue
        try:
            day = _dt.date.fromisoformat(row["Date"])
        except (KeyError, ValueError):
            continue
        bars.append(
            Bar(
                date=day,
                open=_as_float(row.get("Open", "")) or close,
                high=_as_float(row.get("High", "")) or close,
                low=_as_float(row.get("Low", "")) or close,
                close=close,
                volume=_as_float(row.get("Volume", "")),
            )
        )
    bars.sort(key=lambda b: b.date)
    return PriceHistory(ticker.upper(), bars, "stooq.com")


def fetch_yahoo(ticker: str) -> PriceHistory:
    """Daily history from Yahoo Finance's public chart endpoint. No key."""
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        "?range=2y&interval=1d"
    )
    try:
        payload = json.loads(_http_get(url))
    except json.JSONDecodeError as exc:
        raise MarketDataError("Yahoo returned a non-JSON response.") from exc

    chart = (payload or {}).get("chart") or {}
    if chart.get("error"):
        raise MarketDataError(f"Yahoo error for {ticker!r}: {chart['error']}")
    results = chart.get("result") or []
    if not results:
        raise MarketDataError(f"Yahoo returned no series for {ticker!r}.")

    result = results[0]
    stamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]

    bars: list[Bar] = []
    for index, stamp in enumerate(stamps):
        def field(name: str) -> float | None:
            series = quote.get(name) or []
            return _as_float(series[index]) if index < len(series) else None

        close = field("close")
        if close is None:
            continue  # Yahoo pads halted sessions with nulls
        bars.append(
            Bar(
                date=_dt.datetime.fromtimestamp(stamp, _dt.timezone.utc).date(),
                open=field("open") or close,
                high=field("high") or close,
                low=field("low") or close,
                close=close,
                volume=field("volume"),
            )
        )
    bars.sort(key=lambda b: b.date)
    return PriceHistory(ticker.upper(), bars, "finance.yahoo.com")


def fetch_yfinance(ticker: str) -> PriceHistory:
    """Daily history via the optional ``yfinance`` package, if installed."""
    try:
        import yfinance  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on environment
        raise MarketDataError("yfinance is not installed.") from exc

    frame = yfinance.Ticker(ticker).history(period="2y", interval="1d")
    if frame is None or frame.empty:
        raise MarketDataError(f"yfinance returned no rows for {ticker!r}.")

    bars = [
        Bar(
            date=stamp.date(),
            open=float(row["Open"]),
            high=float(row["High"]),
            low=float(row["Low"]),
            close=float(row["Close"]),
            volume=float(row["Volume"]) if "Volume" in row else None,
        )
        for stamp, row in frame.iterrows()
        if row["Close"] == row["Close"]  # drop NaN closes
    ]
    bars.sort(key=lambda b: b.date)
    return PriceHistory(ticker.upper(), bars, "yfinance")


PROVIDERS: dict[str, Callable[[str], PriceHistory]] = {
    "stooq": fetch_stooq,
    "yahoo": fetch_yahoo,
    "yfinance": fetch_yfinance,
}

_DEFAULT_ORDER = ("stooq", "yahoo", "yfinance")


# --------------------------------------------------------------------------
# Caching
# --------------------------------------------------------------------------

def _cache_dir() -> str:
    root = os.environ.get("STOCKCAST_CACHE") or os.path.join(
        os.path.expanduser("~"), ".cache", "stockcast"
    )
    os.makedirs(root, exist_ok=True)
    return root


def _cache_path(ticker: str) -> str:
    safe = "".join(c for c in ticker.upper() if c.isalnum() or c in "-.")
    return os.path.join(_cache_dir(), f"{safe}.json")


def _read_cache(ticker: str) -> PriceHistory | None:
    path = _cache_path(ticker)
    try:
        if time.time() - os.path.getmtime(path) > _CACHE_TTL:
            return None
        with open(path, encoding="utf-8") as handle:
            blob = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    try:
        bars = [
            Bar(
                date=_dt.date.fromisoformat(b["date"]),
                open=b["open"], high=b["high"], low=b["low"],
                close=b["close"], volume=b.get("volume"),
            )
            for b in blob["bars"]
        ]
        return PriceHistory(blob["ticker"], bars, blob["source"] + " (cached)")
    except (KeyError, TypeError, ValueError, MarketDataError):
        return None


def _write_cache(history: PriceHistory) -> None:
    blob = {
        "ticker": history.ticker,
        "source": history.source,
        "bars": [
            {
                "date": b.date.isoformat(), "open": b.open, "high": b.high,
                "low": b.low, "close": b.close, "volume": b.volume,
            }
            for b in history.bars
        ],
    }
    try:
        with open(_cache_path(history.ticker), "w", encoding="utf-8") as handle:
            json.dump(blob, handle)
    except OSError:
        pass  # a cache that cannot be written is not an error worth raising


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def get_history(
    ticker: str,
    providers: Iterable[str] = _DEFAULT_ORDER,
    use_cache: bool = True,
) -> PriceHistory:
    """Fetch daily history for ``ticker``, trying providers in order.

    Raises ``MarketDataError`` listing what every provider said if they all
    fail, so the user can tell a bad symbol from a network problem.
    """
    if use_cache:
        cached = _read_cache(ticker)
        if cached is not None:
            return cached

    failures: list[str] = []
    for name in providers:
        fetch = PROVIDERS.get(name)
        if fetch is None:
            failures.append(f"{name}: no such provider")
            continue
        try:
            history = fetch(ticker)
        except MarketDataError as exc:
            failures.append(f"{name}: {exc}")
            continue
        except Exception as exc:  # a third-party provider may raise anything
            failures.append(f"{name}: unexpected {type(exc).__name__}: {exc}")
            continue
        if use_cache:
            _write_cache(history)
        return history

    raise MarketDataError(
        f"Could not get price history for {ticker!r}. Providers tried:\n  "
        + "\n  ".join(failures)
    )
