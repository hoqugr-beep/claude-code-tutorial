"""Usage ledger and spend caps.

This is the module that makes the business model safe. Two jobs:

1. Record token usage for every API call, tagged with the client it was for.
   You cannot price an engagement, answer "is this client profitable?", or
   notice a runaway loop if you never wrote the numbers down.

2. Refuse to spend past a per-client monthly cap. The cap is checked *before*
   each call, so one client looping a huge document cannot eat your margin.

SQLite by default so this runs with no provisioning. db/schema.sql is the same
shape for Postgres — swap the connection and the SQL carries over.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Iterator

from . import settings


class CapExceeded(RuntimeError):
    """Raised when a client has reached its monthly spend cap."""

    def __init__(self, client_id: str, spent: Decimal, cap: Decimal) -> None:
        self.client_id = client_id
        self.spent = spent
        self.cap = cap
        super().__init__(
            f"client {client_id!r} has spent ${spent:.2f} of its ${cap:.2f} "
            f"monthly cap; refusing further calls until the cap is raised or "
            f"the month rolls over"
        )


# Published list rates in USD per million tokens, as of the date in the README.
#
# VERIFY THESE BEFORE THEY INFORM A CLIENT INVOICE. Per-token pricing changes,
# and promotional rates expire. This table exists so the cap is enforceable at
# all, not as a billing source of truth.
PRICES: dict[str, tuple[Decimal, Decimal]] = {
    #  model id            (input,          output)
    "claude-opus-5": (Decimal("5.00"), Decimal("25.00")),
    "claude-sonnet-5": (Decimal("3.00"), Decimal("15.00")),
    "claude-haiku-4-5": (Decimal("1.00"), Decimal("5.00")),
}

CACHE_WRITE_MULTIPLIER = Decimal("1.25")  # writing to cache costs a premium
CACHE_READ_MULTIPLIER = Decimal("0.10")   # reading from cache is ~10% of input
PER_MILLION = Decimal("1000000")


def cost_usd(model: str, usage) -> Decimal:
    """Compute the list-price cost of one API response.

    `usage.input_tokens` is the *uncached remainder* — cache reads and writes
    are reported separately and must be added, not assumed to be included.
    Getting this wrong silently under-reports spend on cached workloads.
    """
    if model not in PRICES:
        raise KeyError(
            f"no price entry for model {model!r}; add it to PRICES so spend "
            f"caps stay enforceable"
        )
    in_rate, out_rate = PRICES[model]

    uncached = Decimal(getattr(usage, "input_tokens", 0) or 0)
    cache_write = Decimal(getattr(usage, "cache_creation_input_tokens", 0) or 0)
    cache_read = Decimal(getattr(usage, "cache_read_input_tokens", 0) or 0)
    output = Decimal(getattr(usage, "output_tokens", 0) or 0)

    total = (
        uncached * in_rate
        + cache_write * in_rate * CACHE_WRITE_MULTIPLIER
        + cache_read * in_rate * CACHE_READ_MULTIPLIER
        + output * out_rate
    )
    return total / PER_MILLION


@contextmanager
def _connect() -> Iterator[sqlite3.Connection]:
    path = Path(settings.LEDGER_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    """Create the ledger table if it does not exist. Safe to call every run."""
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS api_usage (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id           TEXT    NOT NULL,
                job_id              TEXT    NOT NULL,
                model               TEXT    NOT NULL,
                input_tokens        INTEGER NOT NULL DEFAULT 0,
                output_tokens       INTEGER NOT NULL DEFAULT 0,
                cache_read_tokens   INTEGER NOT NULL DEFAULT 0,
                cache_write_tokens  INTEGER NOT NULL DEFAULT 0,
                cost_usd            TEXT    NOT NULL,
                occurred_at         TEXT    NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_usage_client_time
                ON api_usage (client_id, occurred_at);
            """
        )


def _month_key(when: datetime | None = None) -> str:
    when = when or datetime.now(timezone.utc)
    return when.strftime("%Y-%m")


def month_spend(client_id: str, when: datetime | None = None) -> Decimal:
    """Total spend for one client in the current calendar month (UTC)."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT cost_usd FROM api_usage "
            "WHERE client_id = ? AND substr(occurred_at, 1, 7) = ?",
            (client_id, _month_key(when)),
        ).fetchall()
    return sum((Decimal(r["cost_usd"]) for r in rows), Decimal("0"))


def assert_within_cap(client_id: str, cap_usd: Decimal) -> Decimal:
    """Raise CapExceeded if this client has already reached its cap.

    Called before every API request. Returns spend so far, for logging.
    """
    spent = month_spend(client_id)
    if spent >= cap_usd:
        raise CapExceeded(client_id, spent, cap_usd)
    return spent


def record(client_id: str, job_id: str, model: str, usage) -> Decimal:
    """Write one API call to the ledger. Returns the cost of that call."""
    cost = cost_usd(model, usage)
    with _connect() as conn:
        conn.execute(
            "INSERT INTO api_usage (client_id, job_id, model, input_tokens, "
            "output_tokens, cache_read_tokens, cache_write_tokens, cost_usd, "
            "occurred_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                client_id,
                job_id,
                model,
                getattr(usage, "input_tokens", 0) or 0,
                getattr(usage, "output_tokens", 0) or 0,
                getattr(usage, "cache_read_input_tokens", 0) or 0,
                getattr(usage, "cache_creation_input_tokens", 0) or 0,
                str(cost),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
    return cost


def summary(client_id: str | None = None) -> list[dict]:
    """Per-client spend for the current month. Feed this to your invoicing."""
    query = (
        "SELECT client_id, COUNT(*) AS calls, "
        "SUM(input_tokens) AS input_tokens, SUM(output_tokens) AS output_tokens "
        "FROM api_usage WHERE substr(occurred_at, 1, 7) = ?"
    )
    params: list = [_month_key()]
    if client_id:
        query += " AND client_id = ?"
        params.append(client_id)
    query += " GROUP BY client_id ORDER BY client_id"

    with _connect() as conn:
        rows = conn.execute(query, params).fetchall()

    out = []
    for row in rows:
        out.append(
            {
                "client_id": row["client_id"],
                "calls": row["calls"],
                "input_tokens": row["input_tokens"] or 0,
                "output_tokens": row["output_tokens"] or 0,
                "spend_usd": month_spend(row["client_id"]),
            }
        )
    return out
