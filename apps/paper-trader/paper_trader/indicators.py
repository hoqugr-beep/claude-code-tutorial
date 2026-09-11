"""Incremental technical indicators.

Everything here updates in O(1) per bar so a 30-day, 5-minute, 4-asset run
(34,560 bar-updates) costs almost nothing and a 500-path Monte Carlo stays
practical in pure Python.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field


class EMA:
    def __init__(self, period: int) -> None:
        self.alpha = 2.0 / (period + 1.0)
        self.value: float | None = None

    def update(self, x: float) -> float:
        self.value = x if self.value is None else self.alpha * x + (1 - self.alpha) * self.value
        return self.value


class Wilder:
    """Wilder's smoothing (used by ATR and RSI)."""

    def __init__(self, period: int) -> None:
        self.period = period
        self.value: float | None = None
        self._seed: list[float] = []

    def update(self, x: float) -> float | None:
        if self.value is None:
            self._seed.append(x)
            if len(self._seed) < self.period:
                return None
            self.value = sum(self._seed) / self.period
            return self.value
        self.value = (self.value * (self.period - 1) + x) / self.period
        return self.value


class Rolling:
    """Rolling window with running mean / std / max / min."""

    def __init__(self, period: int) -> None:
        self.period = period
        self.buf: deque[float] = deque(maxlen=period)

    def update(self, x: float) -> None:
        self.buf.append(x)

    @property
    def ready(self) -> bool:
        return len(self.buf) == self.period

    @property
    def mean(self) -> float:
        return sum(self.buf) / len(self.buf) if self.buf else 0.0

    @property
    def std(self) -> float:
        n = len(self.buf)
        if n < 2:
            return 0.0
        m = self.mean
        return math.sqrt(sum((v - m) ** 2 for v in self.buf) / (n - 1))

    @property
    def high(self) -> float:
        return max(self.buf) if self.buf else 0.0

    @property
    def low(self) -> float:
        return min(self.buf) if self.buf else 0.0


@dataclass
class Features:
    """Everything the strategy sees about one symbol at one bar."""

    ready: bool = False
    close: float = 0.0
    atr: float = 0.0
    atr_pct: float = 0.0
    ema_fast: float = 0.0
    ema_slow: float = 0.0
    trend_strength: float = 0.0   # (fast - slow) / atr
    donchian_high: float = 0.0
    donchian_low: float = 0.0
    rsi: float = 50.0
    zscore: float = 0.0
    roc: float = 0.0              # log return over the momentum lookback
    realised_vol: float = 0.0     # per-bar stdev of log returns
    volume_ratio: float = 1.0


class SymbolState:
    """Rolls every indicator forward one bar at a time for a single symbol."""

    # Base periods in 5-minute bars, before `timescale` is applied.  At
    # timescale 1.0 these are 2h/8h EMAs — far too fast for a trend whose
    # half-life is measured in days.  The right time constant is an empirical
    # question, which is why it is a dial.
    FAST, SLOW = 24, 96
    ATR_PERIOD = 48
    DONCHIAN = 72
    RSI_PERIOD = 28
    Z_PERIOD = 96
    MOM_PERIOD = 36
    VOL_PERIOD = 96

    def __init__(self, timescale: float = 1.0) -> None:
        def n(base: int) -> int:
            return max(3, int(round(base * timescale)))

        self.timescale = timescale
        self.fast_n, self.slow_n = n(self.FAST), n(self.SLOW)
        self.mom_n = n(self.MOM_PERIOD)
        self.ema_fast = EMA(self.fast_n)
        self.ema_slow = EMA(self.slow_n)
        self.atr = Wilder(n(self.ATR_PERIOD))
        self.rsi_gain = Wilder(n(self.RSI_PERIOD))
        self.rsi_loss = Wilder(n(self.RSI_PERIOD))
        self.channel_high = Rolling(n(self.DONCHIAN))
        self.channel_low = Rolling(n(self.DONCHIAN))
        self.closes = Rolling(n(self.Z_PERIOD))
        self.rets = Rolling(n(self.VOL_PERIOD))
        self.vols = Rolling(n(self.VOL_PERIOD))
        self.mom_closes: deque[float] = deque(maxlen=self.mom_n + 1)
        self.prev_close: float | None = None
        self.bars_seen = 0
        self.features = Features()

    def update(self, o: float, h: float, l: float, c: float, volume: float) -> Features:
        self.bars_seen += 1
        prev = self.prev_close if self.prev_close is not None else c

        tr = max(h - l, abs(h - prev), abs(l - prev))
        atr = self.atr.update(tr)

        change = c - prev
        self.rsi_gain.update(max(0.0, change))
        self.rsi_loss.update(max(0.0, -change))

        ef = self.ema_fast.update(c)
        es = self.ema_slow.update(c)

        # Donchian is read *before* this bar is added, so it never peeks at
        # the breakout bar itself.
        prior_high = self.channel_high.high
        prior_low = self.channel_low.low
        self.channel_high.update(h)
        self.channel_low.update(l)

        self.closes.update(c)
        self.vols.update(volume)
        if self.prev_close is not None and self.prev_close > 0:
            self.rets.update(math.log(c / self.prev_close))
        self.mom_closes.append(c)

        f = Features()
        f.close = c
        f.atr = atr or 0.0
        f.atr_pct = (f.atr / c) if c else 0.0
        f.ema_fast = ef or c
        f.ema_slow = es or c
        f.trend_strength = ((ef - es) / f.atr) if (ef and es and f.atr > 0) else 0.0
        f.donchian_high = prior_high
        f.donchian_low = prior_low

        g, lo = self.rsi_gain.value, self.rsi_loss.value
        if g is not None and lo is not None:
            f.rsi = 100.0 - 100.0 / (1.0 + (g / lo)) if lo > 0 else 100.0

        sd = self.closes.std
        f.zscore = ((c - self.closes.mean) / sd) if sd > 0 else 0.0
        if len(self.mom_closes) == self.mom_closes.maxlen and self.mom_closes[0] > 0:
            f.roc = math.log(c / self.mom_closes[0])
        f.realised_vol = self.rets.std
        mean_vol = self.vols.mean
        f.volume_ratio = (volume / mean_vol) if mean_vol > 0 else 1.0

        f.ready = (
            self.bars_seen > self.slow_n
            and self.channel_high.ready
            and f.atr > 0
            and self.rets.ready
        )

        self.prev_close = c
        self.features = f
        return f
