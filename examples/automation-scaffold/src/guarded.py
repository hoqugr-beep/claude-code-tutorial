"""The guarded model call.

Everything that talks to the API goes through here, so that four things are
true of every single request without anyone having to remember them:

  1. The client's spend cap is checked *before* the call.
  2. The response is forced into a fixed schema, so downstream code can rely on
     its shape. Deterministic output is the whole reason this workload earned a
     build instead of staying in a chat window.
  3. Token usage is recorded against the client.
  4. Failures surface as typed, actionable errors rather than a stack trace.
"""

from __future__ import annotations

import json
from typing import Any, Type, TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from . import ledger, settings
from .registry import Client

T = TypeVar("T", bound=BaseModel)

# Non-streaming ceiling. Above roughly this, switch to client.messages.stream()
# or requests start hitting HTTP timeouts.
MAX_TOKENS = 16000

_client: anthropic.Anthropic | None = None


def _api() -> anthropic.Anthropic:
    global _client
    if _client is None:
        # max_retries covers 429 and 5xx with exponential backoff. Do not
        # hand-roll a retry loop on top of this.
        _client = anthropic.Anthropic(api_key=settings.api_key(), max_retries=3)
    return _client


class ExtractionFailed(RuntimeError):
    """The model returned something that did not satisfy the schema."""


def _strict(schema: dict[str, Any]) -> dict[str, Any]:
    """Make a Pydantic-generated JSON Schema acceptable to structured outputs.

    Every object needs `additionalProperties: false`, which Pydantic does not
    emit by default. Walks nested definitions and array items too.
    """
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            schema["additionalProperties"] = False
        for value in schema.values():
            _strict(value)
    elif isinstance(schema, list):
        for item in schema:
            _strict(item)
    return schema


def extract(
    client: Client,
    job_id: str,
    document: str,
    schema: Type[T],
) -> T:
    """Run one document through the model and return a validated record.

    Raises CapExceeded before spending anything if the client is at its cap.
    """
    # 1. Cap check, before any spend.
    ledger.assert_within_cap(client.id, client.cap_usd)

    # The instructions are identical for every document this client sends, so
    # they go first and carry a cache breakpoint. On a run of any size the
    # cached prefix reads at a fraction of normal input cost. Keep anything
    # that varies per document *after* this block or the cache never hits.
    system = [
        {
            "type": "text",
            "text": client.instructions,
            "cache_control": {"type": "ephemeral"},
        }
    ]

    try:
        response = _api().messages.create(
            model=client.model,
            max_tokens=MAX_TOKENS,
            system=system,
            thinking={"type": "adaptive"},
            output_config={
                "effort": client.effort,
                "format": {
                    "type": "json_schema",
                    "schema": _strict(schema.model_json_schema()),
                },
            },
            messages=[{"role": "user", "content": document}],
        )
    except anthropic.NotFoundError as exc:
        raise RuntimeError(
            f"model {client.model!r} not found — check the id in clients.yaml"
        ) from exc
    except anthropic.AuthenticationError as exc:
        raise RuntimeError("ANTHROPIC_API_KEY is invalid or revoked") from exc
    except anthropic.RateLimitError as exc:
        # Already retried by the SDK. Surfacing it lets the caller skip this
        # item and continue the batch rather than losing the whole run.
        raise RuntimeError("rate limited after retries; try again later") from exc
    except anthropic.APIStatusError as exc:
        raise RuntimeError(f"API error {exc.status_code}: {exc.message}") from exc
    except anthropic.APIConnectionError as exc:
        raise RuntimeError("could not reach the API — check connectivity") from exc

    # 3. Record what it cost, before anything else can fail.
    ledger.record(client.id, job_id, client.model, response.usage)

    # A refusal is a successful HTTP response with no usable content. Check it
    # before indexing into content, or this crashes on a valid reply.
    if response.stop_reason == "refusal":
        raise ExtractionFailed(
            f"the model declined this document (job {job_id}). Review the "
            f"source material before retrying."
        )
    if response.stop_reason == "max_tokens":
        raise ExtractionFailed(
            f"output hit the {MAX_TOKENS} token ceiling on job {job_id}; the "
            f"record is truncated and was not saved"
        )

    text = next((b.text for b in response.content if b.type == "text"), None)
    if not text:
        raise ExtractionFailed(f"empty response on job {job_id}")

    try:
        return schema.model_validate(json.loads(text))
    except (json.JSONDecodeError, ValidationError) as exc:
        raise ExtractionFailed(
            f"response did not match the schema on job {job_id}: {exc}"
        ) from exc
