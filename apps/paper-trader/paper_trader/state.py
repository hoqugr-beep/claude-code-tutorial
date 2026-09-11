"""Durable state for a paper account that keeps running between sessions.

The container a scheduled run happens in is thrown away afterwards, so the
account has to live in a file that outlives it — committed to the repository
or written to persistent storage. Everything needed to resume exactly where
the last run stopped is here: cash, open positions, closed trades, the
high-water mark the drawdown circuit breaker depends on, and the timestamp of
the last bar already acted on.

That last field is what makes a run idempotent. Re-running after a crash, or
twice in one morning, must not re-trade bars the account has already seen.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
from dataclasses import asdict, dataclass, field, fields

from .config import VenueConfig
from .exchange import Account, Position, Trade

SCHEMA_VERSION = 1


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


@dataclass
class LiveState:
    """Everything that has to survive between runs."""

    schema: int = SCHEMA_VERSION
    created_at: str = field(default_factory=_now)
    updated_at: str = field(default_factory=_now)
    venue: str = "binance"
    symbols: list[str] = field(default_factory=list)
    interval_minutes: int = 5
    preset: str = "ultra-aggressive"
    data_source: str = "live"          # "live" or "simulated"
    starting_cash: float = 1_000.0
    cash: float = 1_000.0
    peak_equity: float = 1_000.0
    last_equity: float = 1_000.0
    positions: list[dict] = field(default_factory=list)
    trades: list[dict] = field(default_factory=list)
    fees_total: float = 0.0
    funding_total: float = 0.0
    liquidations: int = 0
    rejected_orders: int = 0
    last_bar_ts: dict[str, int] = field(default_factory=dict)
    last_aligned_ts: int = 0           # newest bar already acted on
    day_anchor_date: str = ""          # UTC date the daily loss limit is measured from
    day_anchor_equity: float = 0.0     # equity at the start of that day
    equity_history: list[list] = field(default_factory=list)   # [iso, equity]
    daily_marks: list[list] = field(default_factory=list)      # [YYYY-MM-DD, equity]
    journal: list[str] = field(default_factory=list)
    last_run_status: str = "never run"
    last_run_error: str = ""

    # ---- account round trip ---------------------------------------------

    def to_account(self, venue: VenueConfig) -> Account:
        account = Account(cash=self.cash, venue=venue)
        pos_fields = {f.name for f in fields(Position)}
        trade_fields = {f.name for f in fields(Trade)}
        for raw in self.positions:
            account.positions[raw["symbol"]] = Position(
                **{k: v for k, v in raw.items() if k in pos_fields}
            )
        for raw in self.trades:
            account.trades.append(
                Trade(**{k: v for k, v in raw.items() if k in trade_fields})
            )
        account.fees_total = self.fees_total
        account.funding_total = self.funding_total
        account.liquidations = self.liquidations
        account.rejected_orders = self.rejected_orders
        return account

    def absorb(self, account: Account, equity: float) -> None:
        self.cash = account.cash
        self.positions = [asdict(p) for p in account.positions.values()]
        self.trades = [asdict(t) for t in account.trades]
        self.fees_total = account.fees_total
        self.funding_total = account.funding_total
        self.liquidations = account.liquidations
        self.rejected_orders = account.rejected_orders
        self.last_equity = equity
        self.peak_equity = max(self.peak_equity, equity)
        self.updated_at = _now()

    def roll_day_anchor(self, equity: float, today: str | None = None) -> None:
        """Reset the daily-loss baseline when the calendar day changes.

        In a backtest the agent finds day boundaries by counting bars. A live
        run sees only a short window of bars per invocation, so counting would
        restart the "day" on every run and turn a daily loss limit into a
        per-run one. The anchor is therefore a real UTC date held in state.
        """
        day = today or dt.datetime.now(dt.timezone.utc).date().isoformat()
        if self.day_anchor_date != day:
            self.day_anchor_date = day
            self.day_anchor_equity = equity

    def mark_day(self, equity: float, when: dt.date | None = None) -> None:
        """Record one end-of-day equity mark, replacing any mark for that day."""
        day = (when or dt.datetime.now(dt.timezone.utc).date()).isoformat()
        self.daily_marks = [m for m in self.daily_marks if m[0] != day]
        self.daily_marks.append([day, equity])
        self.daily_marks.sort(key=lambda m: m[0])

    # ---- derived ---------------------------------------------------------

    @property
    def total_return(self) -> float:
        return self.last_equity / self.starting_cash - 1.0 if self.starting_cash else 0.0

    @property
    def drawdown(self) -> float:
        return 1.0 - self.last_equity / self.peak_equity if self.peak_equity > 0 else 0.0

    def change_since_previous_mark(self) -> tuple[float, float] | None:
        """(absolute, fractional) change against the second-most-recent mark."""
        if len(self.daily_marks) < 2:
            return None
        prev = self.daily_marks[-2][1]
        if prev <= 0:
            return None
        return self.last_equity - prev, self.last_equity / prev - 1.0


def load(path: str) -> LiveState | None:
    """Load state, or return None if there is none yet."""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    if raw.get("schema") != SCHEMA_VERSION:
        raise ValueError(
            f"{path} has state schema {raw.get('schema')}, this build expects "
            f"{SCHEMA_VERSION}. Refusing to guess at a migration — inspect it by hand."
        )
    known = {f.name for f in fields(LiveState)}
    return LiveState(**{k: v for k, v in raw.items() if k in known})


def save(path: str, state: LiveState) -> None:
    """Write state atomically.

    A half-written state file is worse than no state file: the next run would
    load a corrupt account and trade from it. Write to a temporary file in the
    same directory and rename, which is atomic on POSIX.
    """
    directory = os.path.dirname(os.path.abspath(path)) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".state-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(asdict(state), fh, indent=2, sort_keys=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
