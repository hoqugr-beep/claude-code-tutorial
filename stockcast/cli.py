"""Command-line interface: ``python -m stockcast ORCL 1 week from today``."""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import math
import sys
import textwrap

from .errors import StockcastError
from .predict import DISCLAIMER, Forecast, forecast
from .report import as_dict

__all__ = ["main", "render_text"]

_BAR_WIDTH = 44


def _supports_colour(stream) -> bool:
    return hasattr(stream, "isatty") and stream.isatty()


def _wrap(text: str, indent: str = "  ", width: int = 78) -> str:
    return textwrap.fill(
        text, width=width, initial_indent=indent, subsequent_indent=indent
    )


def _interval_bar(low: float, high: float, spot: float, median: float) -> str:
    """A one-line picture of where the interval sits relative to today."""
    span_low, span_high = min(low, spot), max(high, spot)
    if span_high <= span_low:
        return ""
    def position(value: float) -> int:
        fraction = (value - span_low) / (span_high - span_low)
        return max(0, min(_BAR_WIDTH - 1, round(fraction * (_BAR_WIDTH - 1))))

    cells = ["·"] * _BAR_WIDTH
    for index in range(position(low), position(high) + 1):
        cells[index] = "─"
    cells[position(spot)] = "│"
    cells[position(median)] = "●"
    return "".join(cells)


def render_text(result: Forecast, colour: bool = False) -> str:
    """Render a forecast as plain text for a terminal."""
    bold = "\033[1m" if colour else ""
    dim = "\033[2m" if colour else ""
    reset = "\033[0m" if colour else ""

    low80, high80 = result.interval(0.80)
    low95, high95 = result.interval(0.95)
    query = result.query
    change = result.expected_change_pct

    lines = [
        "",
        f"{bold}{query.ticker}  →  {query.target_date} "
        f"({query.horizon_label}, {query.trading_days} trading sessions){reset}",
        "=" * 78,
        "",
        f"  Last close      {result.spot:,.2f}   "
        f"{dim}({result.last_close_date}, via {result.history.source}){reset}",
        f"  {bold}Median forecast {result.point_estimate:,.2f}   "
        f"({change:+.2f}%){reset}",
        "",
        f"  80% interval    {low80:,.2f}  to  {high80:,.2f}"
        f"   {dim}({(low80 / result.spot - 1) * 100:+.1f}% to "
        f"{(high80 / result.spot - 1) * 100:+.1f}%){reset}",
        f"  95% interval    {low95:,.2f}  to  {high95:,.2f}",
        "",
        f"  {dim}{_interval_bar(low80, high80, result.spot, result.point_estimate)}"
        f"{reset}",
        f"  {dim}│ = today   ● = median   ─ = 80% interval{reset}",
        "",
        f"  P(higher than today)  {result.probability_up:.1%}",
        f"  Annualised volatility {result.volatility.annualized:.1%}"
        f"  {dim}({result.volatility.method} of realized/EWMA over "
        f"{result.volatility.lookback_days} sessions){reset}",
        "",
    ]

    research = result.research
    if result.research_verified and research is not None:
        lines.append(
            f"{bold}Current events{reset}  "
            f"{dim}{research.searches_performed} web searches, "
            f"model {research.model}{reset}"
        )
        lines.append("-" * 78)
        if research.narrative:
            lines.extend(["", _wrap(research.narrative)])
        if research.catalysts:
            lines.append("")
            for catalyst in research.catalysts:
                marker = {"bullish": "▲", "bearish": "▼"}.get(
                    catalyst.direction, "◆"
                )
                lines.append(
                    f"  {marker} [{catalyst.importance:<6}] "
                    f"{catalyst.headline.strip()}"
                )
                if catalyst.source_url:
                    lines.append(f"    {dim}{catalyst.source_url}{reset}")
        if research.scheduled_events:
            lines.extend(["", "  Scheduled inside the window:"])
            lines.extend(f"    · {e}" for e in research.scheduled_events)
        lines.extend([
            "",
            f"  {dim}Research view {research.expected_move_pct:+.1f}% at "
            f"confidence {research.confidence:.2f} → applied drift "
            f"{(math.exp(result.applied_log_drift) - 1) * 100:+.2f}%"
            f"{'  (CAPPED)' if result.bias_was_capped else ''}{reset}",
        ])
        if research.cost_usd:
            lines.append(f"  {dim}Research cost ${research.cost_usd:.2f}{reset}")
        lines.append("")
    else:
        lines.extend([
            f"{bold}Current events{reset}  NOT CONSULTED",
            "-" * 78,
            _wrap(
                result.research_error
                or "Research was disabled, so this is a pure volatility model "
                "with no directional view.",
            ),
            "",
        ])

    if result.warnings:
        lines.append(f"{bold}Warnings{reset}")
        lines.append("-" * 78)
        lines.extend(_wrap(f"! {w}") for w in result.warnings)
        lines.append("")

    lines.extend([_wrap(DISCLAIMER, indent="  "), ""])
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="stockcast",
        description=(
            "Forecast a stock price distribution from price history plus "
            "researched current events."
        ),
        epilog="Example: stockcast ORCL 1 week from today",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "request",
        nargs="*",
        help="Ticker followed by a timeframe, e.g. 'ORCL 1 week from today'.",
    )
    parser.add_argument(
        "--no-research",
        action="store_true",
        help="Skip current-events research; use the volatility model alone.",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of text.")
    parser.add_argument(
        "--model", default="sonnet", help="Model for research (default: sonnet)."
    )
    parser.add_argument(
        "--lookback", type=int, default=252,
        help="Trading sessions of history for the volatility estimate.",
    )
    parser.add_argument(
        "--vol-method", choices=("realized", "ewma", "max"), default="max",
        help="Volatility estimator (default: max, the more conservative).",
    )
    parser.add_argument(
        "--provider", action="append", dest="providers",
        choices=("stooq", "yahoo", "yfinance"),
        help="Force a price provider; repeat to set the fallback order.",
    )
    parser.add_argument(
        "--timeout", type=int, default=420, help="Research timeout in seconds."
    )
    parser.add_argument(
        "--no-cache", action="store_true", help="Bypass the local price cache."
    )
    parser.add_argument(
        "--as-of", help="Pretend today is this ISO date (for testing)."
    )
    parser.add_argument(
        "--serve", action="store_true", help="Start the local web UI instead."
    )
    parser.add_argument("--port", type=int, default=8765, help="Port for --serve.")
    parser.add_argument(
        "--host", default="127.0.0.1", help="Bind address for --serve."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.serve:
        from .web import serve

        serve(host=args.host, port=args.port)
        return 0

    if not args.request:
        build_parser().print_help()
        return 2

    as_of = None
    if args.as_of:
        try:
            as_of = _dt.date.fromisoformat(args.as_of)
        except ValueError:
            print(f"error: --as-of {args.as_of!r} is not an ISO date.", file=sys.stderr)
            return 2

    try:
        result = forecast(
            " ".join(args.request),
            as_of=as_of,
            use_research=not args.no_research,
            lookback=args.lookback,
            volatility_method=args.vol_method,
            providers=tuple(args.providers) if args.providers else None,
            research_model=args.model,
            research_timeout=args.timeout,
            use_cache=not args.no_cache,
        )
    except StockcastError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(as_dict(result), indent=2))
    else:
        print(render_text(result, colour=_supports_colour(sys.stdout)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
