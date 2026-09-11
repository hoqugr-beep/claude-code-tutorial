"""Parse a free-form request like ``ORCL 1 week from today`` into a query."""

from __future__ import annotations

import datetime as _dt
import re
from dataclasses import dataclass

from .calendar_us import is_trading_day, trading_days_between
from .errors import ParseError

__all__ = ["Query", "parse_request", "parse_horizon", "next_trading_day"]

# Ticker symbols: 1-5 letters, optionally with a class suffix (BRK.B) or a
# market suffix (RY.TO). Deliberately strict so that stray English words in
# the request are not mistaken for a symbol.
_TICKER_RE = re.compile(r"^[A-Za-z]{1,5}(?:[.\-][A-Za-z]{1,4})?$")

_UNIT_DAYS = {
    "day": 1,
    "days": 1,
    "d": 1,
    "week": 7,
    "weeks": 7,
    "wk": 7,
    "wks": 7,
    "w": 7,
    "month": 30,
    "months": 30,
    "mo": 30,
    "mos": 30,
    "m": 30,
    "quarter": 91,
    "quarters": 91,
    "q": 91,
    "year": 365,
    "years": 365,
    "y": 365,
    "yr": 365,
    "yrs": 365,
}

_WORD_NUMBERS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "eighteen": 18, "twenty": 20,
}

# Filler that carries no information about ticker or horizon.
_NOISE = {
    "from", "today", "in", "out", "ahead", "later", "time", "the", "next",
    "for", "at", "on", "after", "within", "over", "price", "of", "to", "be",
    "will", "what", "predict", "forecast",
}

# Compact forms such as "1w", "10d", "3mo", "2y".
_COMPACT_RE = re.compile(r"^(\d+)\s*([a-z]+)$")

_MAX_HORIZON_DAYS = 365 * 2


def next_trading_day(day: _dt.date) -> _dt.date:
    """The first trading session on or after ``day``."""
    for _ in range(15):
        if is_trading_day(day):
            return day
        day += _dt.timedelta(days=1)
    raise ParseError(f"No trading session found near {day}.")


@dataclass(frozen=True)
class Query:
    """A fully resolved forecast request.

    ``target_date`` is always a trading session. A request landing on a
    weekend or holiday is rolled forward to the next open session, and
    ``rolled_from`` records the date the user actually asked for.
    """

    ticker: str
    target_date: _dt.date
    as_of: _dt.date
    horizon_label: str
    rolled_from: _dt.date | None = None

    @property
    def calendar_days(self) -> int:
        return (self.target_date - self.as_of).days

    @property
    def trading_days(self) -> int:
        return trading_days_between(self.as_of, self.target_date)


def _coerce_number(token: str) -> int | None:
    if token.isdigit():
        return int(token)
    return _WORD_NUMBERS.get(token)


def parse_horizon(text: str, as_of: _dt.date) -> tuple[_dt.date, str]:
    """Resolve a horizon phrase to a target date and a tidy label.

    Accepts ``1 week``, ``1 week from today``, ``1w``, ``ten days``,
    ``tomorrow``, ``3 months``, or an explicit ISO date ``2026-12-31``.
    """
    cleaned = text.strip().lower()
    if not cleaned:
        raise ParseError("No timeframe given. Try: ORCL 1 week from today")

    # An explicit ISO date wins outright.
    iso = re.search(r"\d{4}-\d{2}-\d{2}", cleaned)
    if iso:
        try:
            target = _dt.date.fromisoformat(iso.group(0))
        except ValueError as exc:
            raise ParseError(f"{iso.group(0)!r} is not a real date.") from exc
        if target <= as_of:
            raise ParseError(
                f"Target date {target} is not in the future (today is {as_of})."
            )
        return target, target.isoformat()

    if cleaned in {"tomorrow", "next day", "1 session"}:
        return as_of + _dt.timedelta(days=1), "tomorrow"

    tokens = [t for t in re.split(r"[\s,]+", cleaned) if t and t not in _NOISE]
    if not tokens:
        raise ParseError(f"Could not find a timeframe in {text!r}.")

    number: int | None = None
    unit: str | None = None

    for token in tokens:
        compact = _COMPACT_RE.match(token)
        if compact and compact.group(2) in _UNIT_DAYS:
            number, unit = int(compact.group(1)), compact.group(2)
            break
        value = _coerce_number(token)
        if value is not None and number is None:
            number = value
            continue
        if token in _UNIT_DAYS and unit is None:
            unit = token
            if number is None:
                number = 1
            break

    if unit is None:
        raise ParseError(
            f"Could not understand the timeframe {text!r}. "
            "Try formats like '1 week', '10 days', '3 months', or '2026-12-31'."
        )

    assert number is not None
    if number <= 0:
        raise ParseError("The timeframe must be a positive amount of time.")

    days = number * _UNIT_DAYS[unit]
    if days > _MAX_HORIZON_DAYS:
        raise ParseError(
            f"Horizon of {days} days is beyond this tool's 2-year limit; "
            "forecast uncertainty is already overwhelming well before that."
        )

    canonical = {1: "day", 7: "week", 30: "month", 91: "quarter", 365: "year"}[
        _UNIT_DAYS[unit]
    ]
    plural = canonical if number == 1 else canonical + "s"
    return as_of + _dt.timedelta(days=days), f"{number} {plural}"


def parse_request(text: str, as_of: _dt.date | None = None) -> Query:
    """Parse a whole request such as ``ORCL 1 week from today``."""
    as_of = as_of or _dt.date.today()
    stripped = text.strip()
    if not stripped:
        raise ParseError("Empty request. Try: ORCL 1 week from today")

    parts = stripped.split(None, 1)
    candidate = parts[0].lstrip("$")
    if not _TICKER_RE.match(candidate):
        raise ParseError(
            f"{parts[0]!r} does not look like a ticker symbol. "
            "Put the symbol first, e.g. 'ORCL 1 week from today'."
        )
    ticker = candidate.upper()

    if len(parts) == 1:
        raise ParseError(
            f"Got ticker {ticker} but no timeframe. Try: '{ticker} 1 week from today'."
        )

    requested, label = parse_horizon(parts[1], as_of)

    # Markets are shut on weekends and holidays; a request for such a date is
    # answered with the next session, since that is the next price that exists.
    target = next_trading_day(requested)
    rolled = requested if target != requested else None
    return Query(
        ticker=ticker,
        target_date=target,
        as_of=as_of,
        horizon_label=label,
        rolled_from=rolled,
    )
