"""Environment configuration.

Every secret comes from the environment. Nothing is read from a file that could
end up in version control, and nothing is hardcoded — swapping between your API
key and a client's is a config change on the host, not a code change.
"""

from __future__ import annotations

import os
from pathlib import Path


class ConfigError(RuntimeError):
    """Raised at startup when required configuration is missing."""


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(
            f"{name} is not set. Copy .env.example, fill it in, and export it "
            f"(or set it in your host's environment variable settings)."
        )
    return value


def _optional(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


# Resolved lazily so that importing this module never explodes — only calling
# api_key() does. Keeps the test suite and --dry-run runnable with no secrets.
def api_key() -> str:
    return _require("ANTHROPIC_API_KEY")


ROOT = Path(__file__).resolve().parent.parent

# SQLite by default so the scaffold runs with zero provisioning. Point
# LEDGER_PATH at a shared volume in production, or swap ledger.py's connection
# for psycopg and use db/schema.sql against Postgres — the SQL is compatible.
LEDGER_PATH = Path(_optional("LEDGER_PATH", str(ROOT / "ledger.db")))

INBOX_DIR = Path(_optional("INBOX_DIR", str(ROOT / "inbox")))
OUTBOX_DIR = Path(_optional("OUTBOX_DIR", str(ROOT / "outbox")))

CLIENTS_FILE = Path(_optional("CLIENTS_FILE", str(ROOT / "clients.yaml")))

# Where failures go. You want to hear about a break before the client does.
ALERT_WEBHOOK = _optional("ALERT_WEBHOOK")

# Optional per-run delivery webhook (results POSTed as JSON).
DELIVERY_WEBHOOK = _optional("DELIVERY_WEBHOOK")
