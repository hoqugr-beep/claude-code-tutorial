"""Per-client configuration.

One entry per paying client. Everything that differs between engagements lives
here rather than in code, so onboarding a second client is a config change.

The `cap_usd` field is the one that protects you. Set it deliberately for every
client — roughly 3-5x their expected monthly usage leaves headroom for a busy
month while still stopping a runaway loop before it costs real money.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

import yaml

from . import settings


@dataclass(frozen=True)
class Client:
    id: str
    name: str
    instructions: str
    cap_usd: Decimal
    # Default to the most capable model. Step down only after your own evals
    # show quality holds on this client's actual documents — that is a
    # deliberate decision per engagement, not a default worth guessing at.
    model: str = "claude-opus-5"
    # Effort trades thoroughness against tokens and latency. Sweep low/medium/
    # high on real cases before settling; prior-engagement defaults rarely
    # transfer.
    effort: str = "high"
    deliver_to: list[str] = field(default_factory=list)

    @property
    def inbox(self) -> Path:
        return Path(settings.INBOX_DIR) / self.id

    @property
    def outbox(self) -> Path:
        return Path(settings.OUTBOX_DIR) / self.id


class RegistryError(RuntimeError):
    pass


def load(path: Path | None = None) -> dict[str, Client]:
    """Read clients.yaml into a dict keyed by client id."""
    path = Path(path or settings.CLIENTS_FILE)
    if not path.exists():
        raise RegistryError(
            f"no client config at {path}. Copy clients.example.yaml to "
            f"clients.yaml and edit it."
        )

    raw = yaml.safe_load(path.read_text()) or {}
    entries = raw.get("clients")
    if not entries:
        raise RegistryError(f"{path} has no 'clients:' entries")

    clients: dict[str, Client] = {}
    for entry in entries:
        try:
            client_id = entry["id"]
            client = Client(
                id=client_id,
                name=entry["name"],
                instructions=entry["instructions"].strip(),
                cap_usd=Decimal(str(entry["cap_usd"])),
                model=entry.get("model", "claude-opus-5"),
                effort=entry.get("effort", "high"),
                deliver_to=list(entry.get("deliver_to", [])),
            )
        except KeyError as exc:
            raise RegistryError(
                f"client entry {entry!r} is missing required field {exc}"
            ) from exc

        if client.id in clients:
            raise RegistryError(f"duplicate client id {client.id!r}")
        clients[client.id] = client

    return clients
