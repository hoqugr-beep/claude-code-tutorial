"""The actual work.

This example turns a folder of invoice documents into structured records. It is
deliberately the shape of a workload that *earned* a build: high volume, near
identical each time, and an output that feeds another system, so it must have
the same fields every run.

Replace `InvoiceRecord` and `INSTRUCTIONS` in clients.yaml with whatever the
engagement actually needs. The surrounding machinery does not change.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from . import alerts, guarded
from .ledger import CapExceeded
from .registry import Client

# Keep schemas flat and simple. Structured outputs support types, enums and
# nested objects, but not numeric or string range constraints — a Pydantic
# `Field(gt=0)` will be stripped, so validate business rules in code instead.


class LineItem(BaseModel):
    description: str
    quantity: float
    unit_price: float


class InvoiceRecord(BaseModel):
    """One extracted invoice. Every field is required so the output shape is
    identical on every run — downstream imports depend on that."""

    supplier_name: str = Field(description="Legal name of the issuing supplier")
    invoice_number: str = Field(description="The supplier's invoice reference")
    invoice_date: str = Field(description="Invoice date in YYYY-MM-DD format")
    currency: str = Field(description="Three-letter ISO currency code")
    subtotal: float
    tax: float
    total: float
    line_items: list[LineItem]
    needs_review: bool = Field(
        description=(
            "True if anything was ambiguous, illegible, or internally "
            "inconsistent — for example if the line items do not sum to the "
            "stated subtotal."
        )
    )
    review_reason: str = Field(
        description="Why review is needed. Empty string if needs_review is false."
    )


@dataclass
class RunResult:
    client_id: str
    processed: list[InvoiceRecord]
    failed: list[tuple[str, str]]  # (source file, reason)
    stopped_early: bool = False

    @property
    def flagged(self) -> list[InvoiceRecord]:
        return [r for r in self.processed if r.needs_review]


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def process(client: Client, limit: int | None = None) -> RunResult:
    """Process every pending document for one client.

    A single bad document must not take down the batch — failures are collected
    and reported, and the run continues. Hitting the spend cap *does* stop the
    run, because continuing would mean failing every remaining item anyway.
    """
    result = RunResult(client_id=client.id, processed=[], failed=[])

    client.inbox.mkdir(parents=True, exist_ok=True)
    documents = sorted(p for p in client.inbox.iterdir() if p.is_file())
    if limit is not None:
        documents = documents[:limit]

    if not documents:
        return result

    for path in documents:
        job_id = f"{client.id}/{path.name}"
        try:
            record = guarded.extract(client, job_id, _read(path), InvoiceRecord)
        except CapExceeded as exc:
            # Out of budget. Stop cleanly and tell the operator — the remaining
            # documents stay in the inbox for the next run.
            alerts.alert(
                "spend cap reached — run stopped",
                str(exc),
                client_id=client.id,
            )
            result.stopped_early = True
            break
        except Exception as exc:  # noqa: BLE001 — one bad doc must not stop the batch
            result.failed.append((path.name, str(exc)))
            continue

        result.processed.append(record)

    if result.failed:
        detail = "\n".join(f"  {name}: {reason}" for name, reason in result.failed)
        alerts.alert(
            f"{len(result.failed)} of {len(documents)} documents failed",
            detail,
            client_id=client.id,
        )

    return result
