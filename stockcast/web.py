"""A dependency-free local web UI, served from the standard library.

Bound to localhost by default. This is a personal tool, not a public service:
it has no authentication and each request can spend money on research, so do
not expose it to a network you do not control.
"""

from __future__ import annotations

import datetime as _dt
import html
import json
import math
import threading
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .errors import StockcastError
from .predict import DISCLAIMER, Forecast, forecast
from .report import as_dict

__all__ = ["serve", "make_server", "render_html"]

_LOCK = threading.Lock()

_STYLE = """
*,*::before,*::after{box-sizing:border-box}
:root{
  --bg:#f6f7f9; --panel:#ffffff; --ink:#12161c; --muted:#5c6672;
  --line:#e2e6ec; --up:#0f7b52; --down:#b4242c; --flat:#6b7280;
  --accent:#2f5fd0; --warn-bg:#fff6e5; --warn-line:#e0a23a;
  --shadow:0 1px 3px rgba(16,22,30,.07),0 8px 24px rgba(16,22,30,.05);
}
@media (prefers-color-scheme:dark){:root{
  --bg:#0f1216; --panel:#171b21; --ink:#e8ecf1; --muted:#98a2b0;
  --line:#262c35; --up:#3fbd85; --down:#f0666e; --flat:#8b94a1;
  --accent:#7aa2f7; --warn-bg:#2a2214; --warn-line:#9a7526;
  --shadow:0 1px 3px rgba(0,0,0,.4);
}}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,
  BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:820px;margin:0 auto;padding:32px 16px 64px}
h1{font-size:20px;margin:0 0 4px;letter-spacing:-.01em}
.sub{color:var(--muted);font-size:13px;margin:0 0 24px}
form{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:24px}
input[type=text]{flex:1 1 340px;min-width:0;padding:11px 13px;font-size:15px;
  border:1px solid var(--line);border-radius:8px;background:var(--panel);
  color:var(--ink)}
input[type=text]:focus{outline:2px solid var(--accent);outline-offset:-1px}
button{padding:11px 20px;font-size:15px;font-weight:550;border:0;border-radius:8px;
  background:var(--accent);color:#fff;cursor:pointer}
button:hover{filter:brightness(1.08)}
label.opt{display:flex;align-items:center;gap:6px;color:var(--muted);font-size:13px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:12px;
  padding:22px;margin-bottom:18px;box-shadow:var(--shadow)}
.head{display:flex;justify-content:space-between;align-items:baseline;
  flex-wrap:wrap;gap:8px;margin-bottom:18px}
.head h2{margin:0;font-size:17px}
.head .when{color:var(--muted);font-size:13px}
.figs{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:16px}
.fig .k{color:var(--muted);font-size:12px;text-transform:uppercase;
  letter-spacing:.05em;margin-bottom:3px}
.fig .v{font-size:25px;font-weight:600;letter-spacing:-.02em;
  font-variant-numeric:tabular-nums}
.fig .n{font-size:12px;color:var(--muted);margin-top:2px}
.up{color:var(--up)}.down{color:var(--down)}.flat{color:var(--flat)}
.range{margin-top:22px}
.track{position:relative;height:34px;margin:10px 0 6px}
.band95,.band80{position:absolute;top:11px;height:12px;border-radius:6px}
.band95{background:color-mix(in srgb,var(--accent) 16%,transparent)}
.band80{background:color-mix(in srgb,var(--accent) 36%,transparent)}
.tick{position:absolute;top:5px;width:2px;height:24px;background:var(--muted)}
.dot{position:absolute;top:9px;width:16px;height:16px;margin-left:-8px;
  border-radius:50%;background:var(--accent);border:2px solid var(--panel)}
.scale{display:flex;justify-content:space-between;color:var(--muted);
  font-size:12px;font-variant-numeric:tabular-nums}
table{width:100%;border-collapse:collapse;font-size:14px}
td,th{padding:7px 0;border-bottom:1px solid var(--line);text-align:left;
  vertical-align:top}
th{color:var(--muted);font-weight:500;width:38%}
td.num{text-align:right;font-variant-numeric:tabular-nums}
h3{font-size:14px;margin:0 0 12px;text-transform:uppercase;
  letter-spacing:.05em;color:var(--muted)}
ul.cat{list-style:none;margin:0;padding:0}
ul.cat li{padding:10px 0;border-bottom:1px solid var(--line)}
ul.cat li:last-child{border-bottom:0}
.mark{font-weight:700;margin-right:7px}
.imp{font-size:11px;color:var(--muted);text-transform:uppercase;
  letter-spacing:.04em;margin-left:7px}
a{color:var(--accent)}
.src{font-size:12px;display:block;margin-top:3px;word-break:break-all}
.warn{background:var(--warn-bg);border:1px solid var(--warn-line);
  border-radius:10px;padding:14px 18px;margin-bottom:18px;font-size:14px}
.warn ul{margin:6px 0 0;padding-left:20px}
.err{border-color:var(--down)}
.disc{color:var(--muted);font-size:12.5px;line-height:1.6}
.narr{margin:0 0 16px;line-height:1.65}
.meta{color:var(--muted);font-size:12px;margin-top:14px}
@media (max-width:560px){.fig .v{font-size:21px}.wrap{padding:20px 14px 48px}}
"""

_EXAMPLES = ("ORCL 1 week from today", "AAPL 3 months", "NVDA 2026-12-31")


def _page(body: str, title: str = "stockcast") -> str:
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)}</title><style>{_STYLE}</style></head>"
        f"<body><div class='wrap'>{body}</div></body></html>"
    )


def _form(request: str = "", research: bool = True) -> str:
    checked = " checked" if research else ""
    examples = " · ".join(
        f"<a href='/?q={urllib.parse.quote(e)}'>{html.escape(e)}</a>"
        for e in _EXAMPLES
    )
    return (
        "<h1>stockcast</h1>"
        "<p class='sub'>A price <em>distribution</em> for a ticker and a "
        "timeframe, from volatility plus researched current events.</p>"
        "<form method='get' action='/'>"
        f"<input type='text' name='q' value='{html.escape(request)}' "
        "placeholder='ORCL 1 week from today' autofocus>"
        "<button type='submit'>Forecast</button>"
        f"<label class='opt'><input type='checkbox' name='research' value='1'"
        f"{checked}> research current events</label>"
        "</form>"
        f"<p class='sub'>Try: {examples}</p>"
    )


def _cls(value: float) -> str:
    return "up" if value > 0.05 else "down" if value < -0.05 else "flat"


def _pct(spot: float, price: float) -> str:
    return f"{(price / spot - 1) * 100:+.1f}%"


def render_html(result: Forecast) -> str:
    """Render a forecast as an HTML fragment."""
    low80, high80 = result.interval(0.80)
    low95, high95 = result.interval(0.95)
    spot, median = result.spot, result.point_estimate
    change = result.expected_change_pct
    query = result.query

    span_low, span_high = min(low95, spot), max(high95, spot)
    span = (span_high - span_low) or 1.0

    def at(value: float) -> float:
        return max(0.0, min(100.0, (value - span_low) / span * 100.0))

    parts = [
        "<div class='card'>",
        "<div class='head'>",
        f"<h2>{html.escape(query.ticker)} on {query.target_date}</h2>",
        f"<span class='when'>{html.escape(query.horizon_label)} · "
        f"{query.trading_days} trading sessions</span>",
        "</div>",
        "<div class='figs'>",
        f"<div class='fig'><div class='k'>Last close</div>"
        f"<div class='v'>{spot:,.2f}</div>"
        f"<div class='n'>{result.last_close_date}</div></div>",
        f"<div class='fig'><div class='k'>Median forecast</div>"
        f"<div class='v {_cls(change)}'>{median:,.2f}</div>"
        f"<div class='n {_cls(change)}'>{change:+.2f}%</div></div>",
        f"<div class='fig'><div class='k'>P(higher)</div>"
        f"<div class='v'>{result.probability_up:.0%}</div>"
        f"<div class='n'>vs today's close</div></div>",
        f"<div class='fig'><div class='k'>Annualised vol</div>"
        f"<div class='v'>{result.volatility.annualized:.0%}</div>"
        f"<div class='n'>{result.volatility.method} estimator</div></div>",
        "</div>",
        "<div class='range'>",
        "<h3>Where the price could land</h3>",
        "<div class='track'>",
        f"<div class='band95' style='left:{at(low95):.2f}%;"
        f"width:{at(high95) - at(low95):.2f}%'></div>",
        f"<div class='band80' style='left:{at(low80):.2f}%;"
        f"width:{at(high80) - at(low80):.2f}%'></div>",
        f"<div class='tick' style='left:{at(spot):.2f}%' title='today'></div>",
        f"<div class='dot' style='left:{at(median):.2f}%' title='median'></div>",
        "</div>",
        f"<div class='scale'><span>{span_low:,.2f}</span>"
        f"<span>{span_high:,.2f}</span></div>",
        "<table style='margin-top:14px'>",
        f"<tr><th>80% interval</th><td class='num'>{low80:,.2f} – {high80:,.2f}"
        f"</td><td class='num'>{_pct(spot, low80)} to {_pct(spot, high80)}</td></tr>",
        f"<tr><th>95% interval</th><td class='num'>{low95:,.2f} – {high95:,.2f}"
        f"</td><td class='num'>{_pct(spot, low95)} to {_pct(spot, high95)}</td></tr>",
        "</table>",
        "</div>",
        f"<p class='meta'>Prices via {html.escape(result.history.source)} · "
        f"volatility from {result.volatility.lookback_days} sessions · "
        f"horizon σ {result.distribution.sigma:.3f}</p>",
        "</div>",
    ]

    if result.warnings:
        items = "".join(f"<li>{html.escape(w)}</li>" for w in result.warnings)
        parts.append(f"<div class='warn'><strong>Read with care</strong><ul>{items}</ul></div>")

    research = result.research
    if result.research_verified and research is not None:
        parts.append("<div class='card'><h3>Current events</h3>")
        if research.narrative:
            parts.append(f"<p class='narr'>{html.escape(research.narrative)}</p>")
        if research.catalysts:
            parts.append("<ul class='cat'>")
            for catalyst in research.catalysts:
                mark, klass = {
                    "bullish": ("▲", "up"),
                    "bearish": ("▼", "down"),
                }.get(catalyst.direction, ("◆", "flat"))
                source = (
                    f"<a class='src' href='{html.escape(catalyst.source_url)}' "
                    f"target='_blank' rel='noopener noreferrer'>"
                    f"{html.escape(catalyst.source_url)}</a>"
                    if catalyst.source_url else ""
                )
                parts.append(
                    f"<li><span class='mark {klass}'>{mark}</span>"
                    f"{html.escape(catalyst.headline)}"
                    f"<span class='imp'>{html.escape(catalyst.importance)}</span>"
                    f"{source}</li>"
                )
            parts.append("</ul>")
        if research.scheduled_events:
            events = "".join(
                f"<li>{html.escape(e)}</li>" for e in research.scheduled_events
            )
            parts.append(f"<h3 style='margin-top:18px'>Scheduled in the window</h3>"
                         f"<ul class='cat'>{events}</ul>")
        applied = (math.exp(result.applied_log_drift) - 1) * 100
        parts.append(
            f"<p class='meta'>{research.searches_performed} verified web searches "
            f"· model {html.escape(research.model)} · research view "
            f"{research.expected_move_pct:+.1f}% at confidence "
            f"{research.confidence:.2f} → applied drift {applied:+.2f}%"
            f"{' (capped)' if result.bias_was_capped else ''}"
            + (f" · ${research.cost_usd:.2f}" if research.cost_usd else "")
            + "</p></div>"
        )
    else:
        reason = result.research_error or (
            "Research was switched off, so this is the volatility model alone "
            "with no directional view."
        )
        parts.append(
            "<div class='card'><h3>Current events — not consulted</h3>"
            f"<p class='narr'>{html.escape(reason)}</p></div>"
        )

    parts.append(f"<p class='disc'>{html.escape(DISCLAIMER)}</p>")
    return "".join(parts)


class _Handler(BaseHTTPRequestHandler):
    server_version = "stockcast"

    def log_message(self, fmt: str, *args) -> None:  # quieter console
        return

    def _send(self, status: int, body: str, content_type: str) -> None:
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path not in ("/", "/api"):
            self._send(404, _page("<h1>Not found</h1>"), "text/html")
            return

        params = urllib.parse.parse_qs(parsed.query)
        request = (params.get("q") or [""])[0].strip()
        use_research = bool(params.get("research")) or "research" in params
        wants_json = parsed.path == "/api"

        if not request:
            if wants_json:
                self._send(400, json.dumps({"error": "missing q"}), "application/json")
            else:
                self._send(200, _page(_form()), "text/html")
            return

        as_of_raw = (params.get("as_of") or [""])[0].strip()
        as_of = None
        if as_of_raw:
            try:
                as_of = _dt.date.fromisoformat(as_of_raw)
            except ValueError:
                as_of = None

        try:
            # Research spends money and hits the network; one at a time.
            with _LOCK:
                result = forecast(
                    request, as_of=as_of, use_research=use_research
                )
        except StockcastError as exc:
            if wants_json:
                self._send(400, json.dumps({"error": str(exc)}), "application/json")
            else:
                self._send(
                    200,
                    _page(
                        _form(request, use_research)
                        + f"<div class='warn err'>{html.escape(str(exc))}</div>"
                    ),
                    "text/html",
                )
            return
        except Exception:  # never leak a traceback to the browser
            traceback.print_exc()
            message = "Something went wrong. See the server console for details."
            if wants_json:
                self._send(500, json.dumps({"error": message}), "application/json")
            else:
                self._send(
                    500,
                    _page(_form(request, use_research)
                          + f"<div class='warn err'>{message}</div>"),
                    "text/html",
                )
            return

        if wants_json:
            self._send(200, json.dumps(as_dict(result), indent=2), "application/json")
        else:
            self._send(
                200,
                _page(
                    _form(request, use_research) + render_html(result),
                    f"{result.query.ticker} · stockcast",
                ),
                "text/html",
            )


def make_server(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    """Build the HTTP server without starting it (useful in tests)."""
    return ThreadingHTTPServer((host, port), _Handler)


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run the local web UI until interrupted."""
    httpd = make_server(host, port)
    print(f"stockcast web UI on http://{host}:{port}  (Ctrl-C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopping")
    finally:
        httpd.server_close()
