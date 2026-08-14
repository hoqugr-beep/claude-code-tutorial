"""Getting results to the client.

The default delivery shape is "results appear where they already work" — the
client opens nothing new and learns nothing new. Here that means a CSV they can
import and a JSON file for anything downstream, written to an outbox directory
you sync to a shared folder.

To deliver by email instead, point this at your transactional mail provider —
the run summary is already assembled for you. Deliberately not implemented here,
because shipping an untested mail path is worse than shipping none.
"""

from __future__ import annotations

import csv
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from . import alerts, settings
from .pipeline import RunResult
from .registry import Client

CSV_COLUMNS = [
    "invoice_number",
    "invoice_date",
    "supplier_name",
    "currency",
    "subtotal",
    "tax",
    "total",
    "needs_review",
    "review_reason",
]


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def write_files(client: Client, result: RunResult) -> list[Path]:
    """Write the run's output to the client's outbox. Returns written paths."""
    if not result.processed:
        return []

    client.outbox.mkdir(parents=True, exist_ok=True)
    stamp = _stamp()
    written: list[Path] = []

    csv_path = client.outbox / f"invoices-{stamp}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for record in result.processed:
            row = record.model_dump()
            writer.writerow({column: row[column] for column in CSV_COLUMNS})
    written.append(csv_path)

    json_path = client.outbox / f"invoices-{stamp}.json"
    json_path.write_text(
        json.dumps([r.model_dump() for r in result.processed], indent=2),
        encoding="utf-8",
    )
    written.append(json_path)

    return written


def summary_text(client: Client, result: RunResult, files: list[Path]) -> str:
    """A short human summary. This is what a person actually reads."""
    lines = [
        f"{client.name} — invoice processing",
        f"{len(result.processed)} processed, {len(result.failed)} failed.",
    ]
    if result.flagged:
        lines.append("")
        lines.append(f"{len(result.flagged)} need a look:")
        for record in result.flagged:
            reason = record.review_reason or "flagged without a stated reason"
            lines.append(f"  {record.invoice_number} ({record.supplier_name}): {reason}")
    if result.failed:
        lines.append("")
        lines.append("Could not be read:")
        for name, reason in result.failed:
            lines.append(f"  {name}: {reason}")
    if result.stopped_early:
        lines.append("")
        lines.append(
            "This run stopped early at the monthly spend cap. Remaining "
            "documents are still queued."
        )
    if files:
        lines.append("")
        lines.append("Files: " + ", ".join(p.name for p in files))
    return "\n".join(lines)


def post_webhook(client: Client, result: RunResult) -> None:
    """Optionally POST results as JSON, for clients wired up via middleware."""
    if not settings.DELIVERY_WEBHOOK:
        return

    payload = json.dumps(
        {
            "client_id": client.id,
            "processed": [r.model_dump() for r in result.processed],
            "failed": [{"source": n, "reason": r} for n, r in result.failed],
        }
    ).encode()

    request = urllib.request.Request(
        settings.DELIVERY_WEBHOOK,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=30).close()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        # Delivery failing is a real incident — the work was done and paid for
        # but never arrived. Alert loudly rather than swallowing it.
        alerts.alert("delivery webhook failed", str(exc), client_id=client.id)


def deliver(client: Client, result: RunResult) -> str:
    files = write_files(client, result)
    post_webhook(client, result)
    return summary_text(client, result, files)
