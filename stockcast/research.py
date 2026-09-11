"""Current-events research, delegated to the Claude Code CLI.

This runs ``claude --print`` as a subprocess, so it authenticates exactly the
way your Claude Code already does — a Pro/Max subscription works, and no
separate API key is needed.

The hard requirement here is *verification*. A language model asked to
"research the news" will happily answer from memory and decorate the answer
with a plausible-looking URL; that output is textually indistinguishable from
genuine research. So this module does not trust the text it gets back. It
reads the execution trace, counts actual web-search tool invocations, and
raises ``ResearchError`` if there were none. A forecast is only ever labelled
as research-informed when searches provably ran.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Any, Sequence

from .errors import ResearchError

__all__ = [
    "Catalyst",
    "ResearchResult",
    "research_ticker",
    "claude_cli_available",
    "RESEARCH_CATEGORIES",
]

RESEARCH_CATEGORIES = (
    "company-specific news, earnings dates, guidance and analyst revisions",
    "central bank policy and interest rate expectations",
    "elections, legislation, tariffs and other policy changes",
    "wars, sanctions and geopolitical disruption",
    "energy and commodity prices",
    "sector and competitor developments",
    "regulatory, antitrust and litigation exposure",
)

# Tool names that count as evidence that the model actually looked things up.
_SEARCH_TOOLS = {"WebSearch", "WebFetch"}

_DEFAULT_TIMEOUT = 420
_DEFAULT_MODEL = "sonnet"
_DEFAULT_BUDGET_USD = 2.0

# How far the research layer is ever allowed to move the forecast, as a
# multiple of the horizon's own standard deviation. Even a maximally
# confident narrative cannot push the median beyond this.
MAX_BIAS_SIGMAS = 1.0
MAX_VOL_MULTIPLIER = 2.0


@dataclass(frozen=True)
class Catalyst:
    """One identified driver of the stock over the forecast window."""

    category: str
    headline: str
    direction: str  # "bullish" | "bearish" | "uncertain"
    importance: str  # "high" | "medium" | "low"
    source_url: str = ""

    @property
    def sign(self) -> int:
        return {"bullish": 1, "bearish": -1}.get(self.direction, 0)


@dataclass
class ResearchResult:
    """Structured output of a verified research pass."""

    ticker: str
    catalysts: list[Catalyst] = field(default_factory=list)
    expected_move_pct: float = 0.0
    confidence: float = 0.0
    volatility_multiplier: float = 1.0
    scheduled_events: list[str] = field(default_factory=list)
    narrative: str = ""
    searches_performed: int = 0
    sources: list[str] = field(default_factory=list)
    model: str = ""
    cost_usd: float | None = None

    @property
    def verified(self) -> bool:
        """True only if the trace proves the web was actually searched."""
        return self.searches_performed > 0


def claude_cli_available() -> bool:
    """True if the ``claude`` executable is on PATH."""
    return shutil.which("claude") is not None


# --------------------------------------------------------------------------
# Prompt
# --------------------------------------------------------------------------

def build_prompt(ticker: str, horizon_label: str, target_date: str) -> str:
    """Build the research prompt.

    Two details matter. First, the web-search tool is named explicitly: with
    a soft instruction like "search the web", the model may skip the tool
    entirely and answer from memory. Second, the prompt states plainly that
    an honest "I could not find this" is the wanted answer when the search
    comes up empty — otherwise the path of least resistance is invention.
    """
    categories = "\n".join(f"  - {c}" for c in RESEARCH_CATEGORIES)
    return f"""You are a financial research assistant gathering evidence for a \
price forecast of {ticker} over the next {horizon_label} (target date \
{target_date}).

Use the WebSearch tool. Run several separate searches to cover these areas:
{categories}

Rules you must follow:
  - Every claim must come from a page you actually retrieved in this session.
  - Never invent a source, a headline, a date, or a number. If searches turn
    up nothing on a category, omit it. Reporting less is correct; inventing
    is a failure.
  - source_url must be a specific article URL you actually opened, not a
    generic landing or quote page.
  - Prefer items published in the last few weeks over older background.

Then output ONE JSON object inside a ```json fenced block, and nothing after \
it:

{{
  "catalysts": [
    {{
      "category": "one of the areas above",
      "headline": "what happened, factually, in one sentence",
      "direction": "bullish" | "bearish" | "uncertain",
      "importance": "high" | "medium" | "low",
      "source_url": "https://the-article-you-actually-read"
    }}
  ],
  "scheduled_events": [
    "dated events inside the forecast window, e.g. 'Q3 earnings 2026-10-14'"
  ],
  "expected_move_pct": <number>,
  "confidence": <number between 0 and 1>,
  "volatility_multiplier": <number between 0.8 and 2.0>,
  "narrative": "<3-5 sentences on what dominates this window and why>"
}}

Guidance on the numbers:
  - expected_move_pct is your net directional view in percent over the whole
    window, not annualised. Be conservative: for a {horizon_label} horizon a
    view beyond a few percent needs an unusually strong, specific reason.
    Use 0 when the news is balanced or thin — that is the common case and an
    honest answer.
  - confidence reflects how much the evidence supports that direction. Use
    values below 0.3 when the evidence is thin or conflicting.
  - volatility_multiplier is above 1.0 only when a known event inside the
    window should widen the range of outcomes (earnings, a central bank
    decision, an election, a court ruling). 1.0 is the default.
"""


# --------------------------------------------------------------------------
# Trace parsing
# --------------------------------------------------------------------------

def _iter_events(stdout: str) -> list[dict[str, Any]]:
    events = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def count_searches(events: Sequence[dict[str, Any]]) -> tuple[int, list[str]]:
    """Count real search-tool invocations and collect their queries.

    Read from ``tool_use`` blocks in the streamed trace rather than from the
    result summary's ``server_tool_use`` counters: those counters track
    server-side tool calls and stay at zero when the search runs client-side,
    so they report zero for a successful run and are useless as evidence.
    """
    count = 0
    queries: list[str] = []
    for event in events:
        if event.get("type") != "assistant":
            continue
        for block in event.get("message", {}).get("content", []) or []:
            if block.get("type") == "tool_use" and block.get("name") in _SEARCH_TOOLS:
                count += 1
                payload = block.get("input") or {}
                query = payload.get("query") or payload.get("url") or ""
                if query:
                    queries.append(str(query))
    return count, queries


def _final_text(events: Sequence[dict[str, Any]]) -> str:
    for event in reversed(events):
        if event.get("type") == "result" and isinstance(event.get("result"), str):
            return event["result"]
    chunks = [
        block.get("text", "")
        for event in events
        if event.get("type") == "assistant"
        for block in event.get("message", {}).get("content", []) or []
        if block.get("type") == "text"
    ]
    return "\n".join(chunks)


def _result_event(events: Sequence[dict[str, Any]]) -> dict[str, Any]:
    for event in reversed(events):
        if event.get("type") == "result":
            return event
    return {}


def extract_json(text: str) -> dict[str, Any]:
    """Pull the JSON object out of the model's final message."""
    fenced = re.findall(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidates = list(fenced)

    # Fall back to the last balanced top-level object in the text.
    depth, start = 0, None
    for index, char in enumerate(text):
        if char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                candidates.append(text[start:index + 1])

    for candidate in reversed(candidates):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise ResearchError("The research step returned no parseable JSON object.")


def _clamp(value: Any, low: float, high: float, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    if number != number:  # NaN
        return default
    return max(low, min(high, number))


def _parse_catalysts(raw: Any) -> list[Catalyst]:
    catalysts: list[Catalyst] = []
    if not isinstance(raw, list):
        return catalysts
    for item in raw:
        if not isinstance(item, dict):
            continue
        headline = str(item.get("headline", "")).strip()
        if not headline:
            continue
        direction = str(item.get("direction", "uncertain")).strip().lower()
        if direction not in {"bullish", "bearish", "uncertain"}:
            direction = "uncertain"
        importance = str(item.get("importance", "medium")).strip().lower()
        if importance not in {"high", "medium", "low"}:
            importance = "medium"
        url = str(item.get("source_url", "")).strip()
        if not url.startswith(("http://", "https://")):
            url = ""
        catalysts.append(
            Catalyst(
                category=str(item.get("category", "general")).strip() or "general",
                headline=headline,
                direction=direction,
                importance=importance,
                source_url=url,
            )
        )
    return catalysts


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def research_ticker(
    ticker: str,
    horizon_label: str,
    target_date: str,
    model: str = _DEFAULT_MODEL,
    timeout: int = _DEFAULT_TIMEOUT,
    budget_usd: float = _DEFAULT_BUDGET_USD,
    cwd: str | None = None,
) -> ResearchResult:
    """Run one verified research pass. Raises ``ResearchError`` on any doubt."""
    if not claude_cli_available():
        raise ResearchError(
            "The 'claude' CLI was not found on PATH. Install Claude Code and "
            "sign in, or run with --no-research for a quantitative-only forecast."
        )

    command = [
        "claude",
        "--print",
        build_prompt(ticker, horizon_label, target_date),
        "--output-format", "stream-json",
        "--verbose",
        "--model", model,
        "--allowedTools", "WebSearch", "WebFetch",
        "--disable-slash-commands",
        "--max-budget-usd", str(budget_usd),
    ]

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            check=False,
        )
    except FileNotFoundError as exc:
        raise ResearchError("Could not execute the 'claude' CLI.") from exc
    except subprocess.TimeoutExpired as exc:
        raise ResearchError(
            f"Research timed out after {timeout}s. Retry, or use --no-research."
        ) from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()[:500]
        raise ResearchError(
            f"The 'claude' CLI exited with status {completed.returncode}. {detail}"
        )

    events = _iter_events(completed.stdout)
    if not events:
        raise ResearchError("The research step produced no readable output.")

    result_event = _result_event(events)
    if result_event.get("is_error"):
        raise ResearchError(
            f"Research run reported an error: {result_event.get('subtype', 'unknown')}"
        )

    searches, queries = count_searches(events)
    if searches == 0:
        denials = result_event.get("permission_denials") or []
        hint = (
            f" The run reported {len(denials)} permission denial(s); web search "
            "may be blocked in this environment."
            if denials else
            " Web search may be unavailable, or the network may be restricted."
        )
        raise ResearchError(
            "Research ran but performed zero web searches, so anything it "
            "returned would be unsourced model recall rather than current "
            "information." + hint
        )

    payload = extract_json(_final_text(events))
    catalysts = _parse_catalysts(payload.get("catalysts"))

    scheduled = [
        str(item).strip()
        for item in (payload.get("scheduled_events") or [])
        if str(item).strip()
    ] if isinstance(payload.get("scheduled_events"), list) else []

    return ResearchResult(
        ticker=ticker,
        catalysts=catalysts,
        expected_move_pct=_clamp(payload.get("expected_move_pct"), -50.0, 50.0, 0.0),
        confidence=_clamp(payload.get("confidence"), 0.0, 1.0, 0.0),
        volatility_multiplier=_clamp(
            payload.get("volatility_multiplier"), 0.8, MAX_VOL_MULTIPLIER, 1.0
        ),
        scheduled_events=scheduled,
        narrative=str(payload.get("narrative", "")).strip(),
        searches_performed=searches,
        sources=[c.source_url for c in catalysts if c.source_url] or queries[:8],
        model=model,
        cost_usd=result_event.get("total_cost_usd"),
    )
