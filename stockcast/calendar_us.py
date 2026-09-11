"""US equity market trading calendar.

Counting trading days matters more than it looks: volatility scales with the
square root of the number of *trading* days, so miscounting a holiday week
quietly widens or narrows every interval the model reports.

This implements the regular NYSE/Nasdaq holiday schedule. It does not model
one-off closures (national days of mourning, weather, 9/11) or half-days,
which do not close the market and so do not change the day count.
"""

from __future__ import annotations

import datetime as _dt
from functools import lru_cache

__all__ = ["easter_sunday", "market_holidays", "is_trading_day", "trading_days_between"]


def easter_sunday(year: int) -> _dt.date:
    """Return Easter Sunday for ``year`` in the Gregorian calendar.

    Uses the Anonymous Gregorian computus (Meeus/Jones/Butcher). Needed only
    to locate Good Friday, the one moveable market holiday.
    """
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month, day = divmod(h + l - 7 * m + 114, 31)
    return _dt.date(year, month, day + 1)


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> _dt.date:
    """The ``n``-th ``weekday`` (Mon=0) of a month; ``n=-1`` means the last."""
    if n > 0:
        first = _dt.date(year, month, 1)
        offset = (weekday - first.weekday()) % 7
        return first + _dt.timedelta(days=offset + 7 * (n - 1))
    if month == 12:
        last = _dt.date(year, 12, 31)
    else:
        last = _dt.date(year, month + 1, 1) - _dt.timedelta(days=1)
    return last - _dt.timedelta(days=(last.weekday() - weekday) % 7)


def _observed(day: _dt.date) -> _dt.date:
    """Apply the weekend-observance rule for fixed-date holidays.

    A Saturday holiday is observed the preceding Friday, a Sunday holiday the
    following Monday.
    """
    if day.weekday() == 5:
        return day - _dt.timedelta(days=1)
    if day.weekday() == 6:
        return day + _dt.timedelta(days=1)
    return day


@lru_cache(maxsize=64)
def market_holidays(year: int) -> frozenset[_dt.date]:
    """Regular US equity market closures for ``year``, as observed dates."""
    days = {
        _observed(_dt.date(year, 1, 1)),                  # New Year's Day
        _nth_weekday(year, 1, 0, 3),                      # MLK Jr. Day
        _nth_weekday(year, 2, 0, 3),                      # Washington's Birthday
        easter_sunday(year) - _dt.timedelta(days=2),      # Good Friday
        _nth_weekday(year, 5, 0, -1),                     # Memorial Day
        _observed(_dt.date(year, 7, 4)),                  # Independence Day
        _nth_weekday(year, 9, 0, 1),                      # Labor Day
        _nth_weekday(year, 11, 3, 4),                     # Thanksgiving
        _observed(_dt.date(year, 12, 25)),                # Christmas Day
    }
    # Juneteenth became a market holiday in 2022.
    if year >= 2022:
        days.add(_observed(_dt.date(year, 6, 19)))
    return frozenset(days)


def is_trading_day(day: _dt.date) -> bool:
    """True if US equity markets have a regular session on ``day``."""
    return day.weekday() < 5 and day not in market_holidays(day.year)


def trading_days_between(start: _dt.date, end: _dt.date) -> int:
    """Number of trading sessions after ``start`` up to and including ``end``.

    Returns 0 when ``end`` is on or before ``start``. The count is
    exclusive of the start date because a forecast is made *from* the last
    observed close.
    """
    if end <= start:
        return 0
    count = 0
    day = start + _dt.timedelta(days=1)
    while day <= end:
        if is_trading_day(day):
            count += 1
        day += _dt.timedelta(days=1)
    return count
