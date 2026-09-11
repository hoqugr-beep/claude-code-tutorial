"""Render a run into a self-contained HTML report.

No external libraries, no CDN, no network: everything is inline SVG and a few
lines of vanilla JS, so the file opens from disk and keeps working forever.

Colours come from a validated categorical palette (blue / orange / aqua / red),
declared once as CSS custom properties and referenced by role, with dark-mode
steps chosen for the dark surface rather than flipped automatically.
"""

from __future__ import annotations

import html
import math
from dataclasses import dataclass

from .config import BARS_PER_DAY
from .metrics import Summary, max_drawdown, percentile

# --------------------------------------------------------------------------
# SVG helpers
# --------------------------------------------------------------------------

def _fmt_money(x: float) -> str:
    if abs(x) >= 1000:
        return f"${x:,.0f}"
    if abs(x) >= 1:
        return f"${x:,.2f}"
    return f"${x:.4f}"


def _fmt_axis(x: float) -> str:
    """Compact money for an axis tick: no cents unless the scale needs them."""
    if abs(x) < 1e-9:
        return "$0"
    if abs(x) >= 100:
        return f"${x:,.0f}"
    if abs(x) >= 1:
        return f"${x:,.2f}"
    return f"${x:.4f}"


def _fmt_pct(x: float) -> str:
    return f"{x:.0f}%"


def _nice_ticks(lo: float, hi: float, count: int = 5) -> list[float]:
    if hi <= lo:
        return [lo]
    raw = (hi - lo) / count
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            step = m * mag
            break
    else:
        step = 10 * mag
    start = math.ceil(lo / step) * step
    out = []
    v = start
    while v <= hi + 1e-9:
        out.append(round(v, 10))
        v += step
    return out


def line_chart(
    series: list[float],
    *,
    width: int = 760,
    height: int = 300,
    baseline: float | None = None,
    label: str = "Equity",
    x_label: str = "Day",
    bars_per_x: int = BARS_PER_DAY,
    color: str = "var(--series-1)",
    chart_id: str = "chart",
    value_fmt=_fmt_axis,
) -> str:
    """A single-series line with a crosshair readout.  One series, no legend —
    the heading names it."""
    if not series:
        return "<p class='muted'>No data.</p>"
    pad_l, pad_r, pad_t, pad_b = 62, 16, 14, 34
    w, h = width - pad_l - pad_r, height - pad_t - pad_b
    lo, hi = min(series), max(series)
    if baseline is not None:
        lo, hi = min(lo, baseline), max(hi, baseline)
    span = (hi - lo) or max(abs(hi), 1.0)
    lo -= span * 0.08
    hi += span * 0.08

    def sx(i: int) -> float:
        return pad_l + (i / max(1, len(series) - 1)) * w

    def sy(v: float) -> float:
        return pad_t + (1 - (v - lo) / (hi - lo)) * h

    step = max(1, len(series) // 900)
    pts = " ".join(f"{sx(i):.2f},{sy(series[i]):.2f}" for i in range(0, len(series), step))
    pts += f" {sx(len(series) - 1):.2f},{sy(series[-1]):.2f}"

    grid = []
    for t in _nice_ticks(lo, hi):
        y = sy(t)
        grid.append(f"<line class='grid' x1='{pad_l}' y1='{y:.1f}' x2='{pad_l + w}' y2='{y:.1f}'/>")
        grid.append(f"<text class='tick' x='{pad_l - 8}' y='{y + 4:.1f}' text-anchor='end'>{value_fmt(t)}</text>")

    xticks = []
    n_days = max(1, len(series) // bars_per_x)
    stride = max(1, n_days // 6)
    for d in range(0, n_days + 1, stride):
        i = min(len(series) - 1, d * bars_per_x)
        xticks.append(
            f"<text class='tick' x='{sx(i):.1f}' y='{pad_t + h + 22}' text-anchor='middle'>{d}</text>"
        )

    base_line = ""
    baseline_label = f"start {value_fmt(baseline)}" if baseline is not None else ""
    if baseline is not None:
        by = sy(baseline)
        base_line = (
            f"<line class='baseline' x1='{pad_l}' y1='{by:.1f}' x2='{pad_l + w}' y2='{by:.1f}'/>"
            f"<text class='tick baseline-label' x='{pad_l + w}' y='{by - 6:.1f}' "
            f"text-anchor='end'>{baseline_label}</text>"
        )

    data = ",".join(f"{v:.4f}" for v in series)
    unit = "pct" if value_fmt is _fmt_pct else "money"
    return f"""
<figure class="chart">
  <svg viewBox="0 0 {width} {height}" role="img" aria-label="{html.escape(label)} over time"
       class="linechart" id="{chart_id}" data-series="{data}"
       data-pad="{pad_l},{pad_t},{w},{h}" data-lo="{lo}" data-hi="{hi}"
       data-perx="{bars_per_x}" data-unit="{unit}" preserveAspectRatio="xMidYMid meet">
    {''.join(grid)}
    {''.join(xticks)}
    {base_line}
    <polyline class="series" points="{pts}" style="stroke:{color}"/>
    <g class="crosshair" hidden>
      <line class="cross-x" y1="{pad_t}" y2="{pad_t + h}"/>
      <circle class="cross-dot" r="4" style="fill:{color}"/>
    </g>
    <rect class="hit" x="{pad_l}" y="{pad_t}" width="{w}" height="{h}" fill="transparent"/>
    <text class="axis-title" x="{pad_l + w / 2}" y="{height - 2}" text-anchor="middle">{html.escape(x_label)}</text>
  </svg>
  <div class="tooltip" hidden></div>
</figure>"""


def bar_chart(
    labels: list[str],
    values: list[float],
    *,
    width: int = 760,
    height: int = 260,
    diverging: bool = True,
    value_fmt=_fmt_axis,
    chart_id: str = "bars",
) -> str:
    """Horizontal-baseline bars.  Diverging colours mean sign, not identity."""
    if not values:
        return "<p class='muted'>No data.</p>"
    pad_l, pad_r, pad_t, pad_b = 62, 16, 16, 46
    w, h = width - pad_l - pad_r, height - pad_t - pad_b
    lo = min(0.0, min(values))
    hi = max(0.0, max(values))
    span = (hi - lo) or 1.0
    lo -= span * 0.1
    hi += span * 0.1

    def sy(v: float) -> float:
        return pad_t + (1 - (v - lo) / (hi - lo)) * h

    n = len(values)
    slot = w / n
    bw = min(74.0, slot * 0.62)
    zero = sy(0.0)
    grid = []
    for t in _nice_ticks(lo, hi):
        y = sy(t)
        grid.append(f"<line class='grid' x1='{pad_l}' y1='{y:.1f}' x2='{pad_l + w}' y2='{y:.1f}'/>")
        grid.append(f"<text class='tick' x='{pad_l - 8}' y='{y + 4:.1f}' text-anchor='end'>{value_fmt(t)}</text>")

    bars = []
    for i, (lab, v) in enumerate(zip(labels, values)):
        cx = pad_l + slot * (i + 0.5)
        y = sy(v)
        top, bot = (y, zero) if v >= 0 else (zero, y)
        colour = "var(--series-1)" if not diverging else (
            "var(--pos)" if v >= 0 else "var(--neg)"
        )
        bars.append(
            f"<g class='bar'><rect x='{cx - bw / 2:.1f}' y='{top:.1f}' width='{bw:.1f}' "
            f"height='{max(1.0, bot - top):.1f}' rx='4' style='fill:{colour}'>"
            f"<title>{html.escape(lab)}: {value_fmt(v)}</title></rect>"
            f"<text class='barval' x='{cx:.1f}' y='{(top - 7) if v >= 0 else (bot + 15):.1f}' "
            f"text-anchor='middle'>{value_fmt(v)}</text>"
            f"<text class='tick' x='{cx:.1f}' y='{pad_t + h + 20}' text-anchor='middle'>{html.escape(lab)}</text></g>"
        )
    return f"""
<figure class="chart">
  <svg viewBox="0 0 {width} {height}" role="img" class="barchart" id="{chart_id}"
       preserveAspectRatio="xMidYMid meet">
    {''.join(grid)}
    <line class="zero" x1="{pad_l}" y1="{zero:.1f}" x2="{pad_l + w}" y2="{zero:.1f}"/>
    {''.join(bars)}
  </svg>
</figure>"""


def histogram(
    values: list[float],
    *,
    start: float,
    bins: int = 26,
    width: int = 760,
    height: int = 280,
    chart_id: str = "hist",
) -> str:
    """Distribution of final equity, coloured by whether the month made money."""
    if not values:
        return "<p class='muted'>No data.</p>"
    lo, hi = min(values), max(values)
    if hi <= lo:
        hi = lo + 1.0
    edges = [lo + (hi - lo) * i / bins for i in range(bins + 1)]
    counts = [0] * bins
    for v in values:
        k = min(bins - 1, int((v - lo) / (hi - lo) * bins))
        counts[k] += 1

    pad_l, pad_r, pad_t, pad_b = 54, 16, 16, 46
    w, h = width - pad_l - pad_r, height - pad_t - pad_b
    top = max(counts) or 1
    slot = w / bins
    grid = []
    for t in _nice_ticks(0, top, 4):
        y = pad_t + (1 - t / top) * h
        grid.append(f"<line class='grid' x1='{pad_l}' y1='{y:.1f}' x2='{pad_l + w}' y2='{y:.1f}'/>")
        grid.append(f"<text class='tick' x='{pad_l - 8}' y='{y + 4:.1f}' text-anchor='end'>{t:.0f}</text>")

    bars = []
    for i, c in enumerate(counts):
        if c == 0:
            continue
        x = pad_l + slot * i + 1
        bh = (c / top) * h
        y = pad_t + h - bh
        mid = (edges[i] + edges[i + 1]) / 2
        colour = "var(--pos)" if mid >= start else "var(--neg)"
        bars.append(
            f"<rect class='hbar' x='{x:.1f}' y='{y:.1f}' width='{max(1.0, slot - 2):.1f}' "
            f"height='{bh:.1f}' rx='3' style='fill:{colour}'>"
            f"<title>{_fmt_axis(edges[i])} – {_fmt_axis(edges[i + 1])}: {c} of {len(values)} runs</title></rect>"
        )

    sx = pad_l + (start - lo) / (hi - lo) * w
    marker = ""
    if lo <= start <= hi:
        marker = (
            f"<line class='baseline' x1='{sx:.1f}' y1='{pad_t}' x2='{sx:.1f}' y2='{pad_t + h}'/>"
            f"<text class='tick baseline-label' x='{sx:.1f}' y='{pad_t - 3}' text-anchor='middle'>"
            f"break-even</text>"
        )
    xticks = "".join(
        f"<text class='tick' x='{pad_l + w * k / 4:.1f}' y='{pad_t + h + 20}' "
        f"text-anchor='middle'>{_fmt_axis(lo + (hi - lo) * k / 4)}</text>"
        for k in range(5)
    )
    return f"""
<figure class="chart">
  <svg viewBox="0 0 {width} {height}" role="img" class="hist" id="{chart_id}"
       preserveAspectRatio="xMidYMid meet">
    {''.join(grid)}{''.join(bars)}{marker}{xticks}
    <text class="axis-title" x="{pad_l + w / 2}" y="{height - 2}" text-anchor="middle">Final equity after 30 days</text>
  </svg>
</figure>"""


# --------------------------------------------------------------------------
# Page
# --------------------------------------------------------------------------

# A <link> rather than a CSS @import: an @import blocks the whole stylesheet on
# a remote fetch, so the page renders as nothing at all when the font host is
# slow or unreachable.  A link degrades to the fallback stack instead.
FONT_LINK = (
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
    "family=IBM+Plex+Mono:wght@400;500&"
    "family=IBM+Plex+Sans:wght@400;500;600&"
    'family=IBM+Plex+Serif:wght@600&display=swap">'
)

# IBM Plex, used as a superfamily: Serif for headings (this reads as a risk-desk
# research note, which is what it is), Sans for prose, Mono for every figure —
# a trading blotter sets its numbers monospaced, so the report does too.
CSS = """
:root {
  color-scheme: light;
  --bg: #faf9f7; --surface-1: #fcfcfb; --surface-2: #f2f1ed;
  --border: #e2e0da; --text-primary: #0b0b0b; --text-secondary: #52514e;
  --text-muted: #7a7873;
  --series-1: #2a78d6; --series-2: #eb6834; --series-3: #1baf7a; --series-4: #e34948;
  --pos: #1baf7a; --neg: #e34948; --warn: #eda100;
  --grid: #e6e4de;
  --mono: "IBM Plex Mono", ui-monospace, SFMono-Regular, Menlo, monospace;
  --sans: "IBM Plex Sans", ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif;
  --serif: "IBM Plex Serif", Georgia, "Times New Roman", serif;
}
@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    color-scheme: dark;
    --bg: #131312; --surface-1: #1a1a19; --surface-2: #232321;
    --border: #33332f; --text-primary: #ffffff; --text-secondary: #c3c2b7;
    --text-muted: #918f86;
    --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70; --series-4: #e66767;
    --pos: #199e70; --neg: #e66767; --warn: #c98500;
    --grid: #2c2c29;
  }
}
:root[data-theme="dark"] {
  color-scheme: dark;
  --bg: #131312; --surface-1: #1a1a19; --surface-2: #232321;
  --border: #33332f; --text-primary: #ffffff; --text-secondary: #c3c2b7;
  --text-muted: #918f86;
  --series-1: #3987e5; --series-2: #d95926; --series-3: #199e70; --series-4: #e66767;
  --pos: #199e70; --neg: #e66767; --warn: #c98500;
  --grid: #2c2c29;
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
body {
  margin: 0; background: var(--bg); color: var(--text-primary);
  font: 400 15px/1.65 var(--sans);
  -webkit-font-smoothing: antialiased;
}
.wrap { max-width: 940px; margin: 0 auto; padding-block: 28px; padding-left: 20px; padding-right: 20px; }
h1 { font: 600 32px/1.18 var(--serif); margin: 0 0 8px; letter-spacing: -0.012em; text-wrap: balance; }
h2 { font: 600 21px/1.3 var(--serif); margin: 44px 0 4px; text-wrap: balance; }
h3 { font: 600 14px/1.4 var(--sans); margin: 22px 0 6px; color: var(--text-secondary);
     text-transform: uppercase; letter-spacing: 0.07em; }
p { color: var(--text-secondary); margin: 9px 0; max-width: 70ch; }
.lede { font-size: 16.5px; line-height: 1.6; color: var(--text-secondary); margin-bottom: 4px; max-width: 66ch; }
.muted { color: var(--text-muted); font-size: 13px; }
a { color: var(--series-1); }
.banner {
  display: flex; gap: 10px; align-items: flex-start;
  border: 1px solid var(--warn); border-left-width: 4px; border-radius: 8px;
  background: var(--surface-1); padding: 12px 14px; margin: 18px 0 6px;
}
.banner strong { color: var(--text-primary); }
.banner p { margin: 2px 0 0; font-size: 13.5px; }
.tiles { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; margin: 20px 0 4px; }
@media (max-width: 620px) { .tiles { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
.tile { background: var(--surface-1); border: 1px solid var(--border); border-radius: 10px; padding: 12px 14px; }
.tile .k { font: 500 11px/1.3 var(--mono); text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-muted); }
.tile .v { font: 500 25px/1.25 var(--mono); letter-spacing: -0.01em; margin-top: 5px; font-variant-numeric: tabular-nums; }
.tile .s { font-size: 12.5px; color: var(--text-muted); margin-top: 1px; }
.v.pos { color: var(--pos); } .v.neg { color: var(--neg); }
.card { background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px; padding: 16px 18px; margin: 14px 0; }
.chart { margin: 6px 0 0; position: relative; }
.chart svg { width: 100%; height: auto; display: block; overflow: visible; }
.grid { stroke: var(--grid); stroke-width: 1; }
.zero { stroke: var(--text-muted); stroke-width: 1.5; }
.baseline { stroke: var(--text-muted); stroke-width: 1.5; stroke-dasharray: 4 4; }
.baseline-label, .tick { fill: var(--text-muted); font-size: 11px; font-family: var(--mono); }
.axis-title { fill: var(--text-muted); font-size: 11.5px; }
.barval { fill: var(--text-secondary); font-size: 11px; font-family: var(--mono); }
.series { fill: none; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.cross-x { stroke: var(--text-muted); stroke-width: 1; stroke-dasharray: 3 3; }
.cross-dot { stroke: var(--surface-1); stroke-width: 2; }
.tooltip {
  position: absolute; pointer-events: none; background: var(--surface-2);
  border: 1px solid var(--border); border-radius: 7px; padding: 6px 9px;
  font: 12px/1.45 var(--mono); color: var(--text-primary); white-space: nowrap;
  box-shadow: 0 4px 14px rgba(0,0,0,.12); transform: translate(-50%, -120%); z-index: 5;
}
table { width: 100%; border-collapse: collapse; font-size: 13.5px; margin-top: 8px; }
td { font-family: var(--mono); font-size: 12.5px; }
td:first-child { font-family: var(--sans); font-size: 13.5px; }
th, td { text-align: right; padding: 7px 9px; border-bottom: 1px solid var(--border); font-variant-numeric: tabular-nums; }
th:first-child, td:first-child { text-align: left; font-variant-numeric: normal; }
th { color: var(--text-muted); font: 500 11px/1.4 var(--mono); text-transform: uppercase; letter-spacing: 0.07em; }
td.pos { color: var(--pos); } td.neg { color: var(--neg); }
.scroll { overflow-x: auto; }
.journal { font-family: var(--mono); font-size: 12.5px; }
.journal li { margin: 0 0 9px; color: var(--text-secondary); list-style: none; padding-left: 12px; border-left: 2px solid var(--border); }
.journal .t { color: var(--text-muted); }
.journal li.entry { border-left-color: var(--series-1); }
.journal li.exit { border-left-color: var(--text-muted); }
.journal li.liquidation, .journal li.halt { border-left-color: var(--neg); }
.journal li.pause { border-left-color: var(--warn); }
.journal li.pyramid { border-left-color: var(--series-3); }
ul.plain { padding-left: 18px; }
ul.plain li { color: var(--text-secondary); margin: 5px 0; }
footer { margin-top: 44px; padding-top: 16px; border-top: 1px solid var(--border); }
@media (max-width: 560px) {
  h1 { font-size: 24px; }
  .tile .v { font-size: 21px; }
}
"""

JS = """
document.querySelectorAll('svg.linechart').forEach(function (svg) {
  var fig = svg.closest('.chart');
  var tip = fig.querySelector('.tooltip');
  var cross = svg.querySelector('.crosshair');
  var dot = svg.querySelector('.cross-dot');
  var xline = svg.querySelector('.cross-x');
  var data = svg.dataset.series.split(',').map(Number);
  var p = svg.dataset.pad.split(',').map(Number);
  var padL = p[0], padT = p[1], w = p[2], h = p[3];
  var lo = +svg.dataset.lo, hi = +svg.dataset.hi, perX = +svg.dataset.perx;
  var unit = svg.dataset.unit;
  var money = function (v) {
    if (unit === 'pct') { return v.toFixed(1) + '%'; }
    return '$' + v.toLocaleString(undefined, {maximumFractionDigits: Math.abs(v) < 10 ? 2 : 0});
  };
  function move(evt) {
    var pt = svg.getBoundingClientRect();
    var scale = svg.viewBox.baseVal.width / pt.width;
    var x = (evt.clientX - pt.left) * scale;
    var frac = Math.min(1, Math.max(0, (x - padL) / w));
    var i = Math.round(frac * (data.length - 1));
    var v = data[i];
    var cx = padL + (i / (data.length - 1)) * w;
    var cy = padT + (1 - (v - lo) / (hi - lo)) * h;
    cross.removeAttribute('hidden');
    dot.setAttribute('cx', cx); dot.setAttribute('cy', cy);
    xline.setAttribute('x1', cx); xline.setAttribute('x2', cx);
    tip.removeAttribute('hidden');
    tip.textContent = 'Day ' + (i / perX).toFixed(1) + '  ·  ' + money(v);
    tip.style.left = (cx / scale) + 'px';
    tip.style.top = (cy / scale) + 'px';
  }
  svg.addEventListener('mousemove', move);
  svg.addEventListener('touchmove', function (e) { move(e.touches[0]); e.preventDefault(); }, {passive: false});
  svg.addEventListener('mouseleave', function () {
    cross.setAttribute('hidden', ''); tip.setAttribute('hidden', '');
  });
});
"""


@dataclass
class ReportData:
    """Everything the report renders."""

    result: object                  # RunResult of the headline path
    summary: Summary
    distribution: object            # montecarlo.Distribution
    path_equities: list[float]      # final equity of every Monte Carlo path
    sensitivity: list[tuple[float, object]]   # (predictability, Distribution)
    risk_sweep: list[tuple[float, object]]    # (target volatility, Distribution)
    comparison: list[tuple[str, object]]      # (preset name, Distribution)
    per_asset: dict[str, float]
    generated: str


def _tile(k: str, v: str, s: str = "", cls: str = "") -> str:
    return (f"<div class='tile'><div class='k'>{html.escape(k)}</div>"
            f"<div class='v {cls}'>{html.escape(v)}</div>"
            f"<div class='s'>{html.escape(s)}</div></div>")


def _pct(x: float) -> str:
    return f"{x:+.1%}"


def render(data: ReportData, standalone: bool = True) -> str:
    r, s, d = data.result, data.summary, data.distribution
    cfg = r.config
    start = cfg.risk.starting_cash

    dd_curve = []
    peak = r.equity_curve[0]
    for v in r.equity_curve:
        peak = max(peak, v)
        dd_curve.append(-(1.0 - v / peak) * 100 if peak > 0 else 0.0)

    verdict_cls = "pos" if s.total_return > 0 else "neg"
    tiles = "".join([
        _tile("Final equity", _fmt_money(s.final_equity), f"from {_fmt_money(start)}", verdict_cls),
        _tile("30-day return", _pct(s.total_return), "this path only", verdict_cls),
        _tile("Max drawdown", f"{s.max_drawdown:.1%}", "peak to trough", "neg"),
        _tile("Trades", f"{s.trades:,}", f"{s.win_rate:.0%} winners"),
        _tile("Costs paid", _fmt_money(s.fees_paid + max(0.0, s.funding_paid)),
              f"{(s.fees_paid + max(0.0, s.funding_paid)) / start:.0%} of starting capital", "neg"),
        _tile("Liquidations", f"{s.liquidations}", "forced closes"),
    ])

    mc_tiles = "".join([
        _tile("Median outcome", _fmt_money(d.median), f"across {d.n} market paths"),
        _tile("Chance of profit", f"{d.prob_profit:.0%}", "ends above $1,000",
              "pos" if d.prob_profit > 0.5 else "neg"),
        _tile("Chance of doubling", f"{d.prob_double:.0%}", "ends above $2,000"),
        _tile("Chance of ruin", f"{d.prob_ruin:.0%}", "ends below $100", "neg"),
        _tile("5th percentile", _fmt_money(d.p05), "1 month in 20 is worse", "neg"),
        _tile("95th percentile", _fmt_money(d.p95), "1 month in 20 is better", "pos"),
    ])

    sens_rows = "".join(
        f"<tr><td>{p:.2f}{' — efficient market' if p == 0 else ''}</td>"
        f"<td>{_fmt_money(dist.median)}</td><td>{_fmt_money(dist.p05)}</td>"
        f"<td>{_fmt_money(dist.p95)}</td>"
        f"<td class='{'pos' if dist.prob_profit > 0.5 else 'neg'}'>{dist.prob_profit:.0%}</td>"
        f"<td>{dist.prob_ruin:.0%}</td></tr>"
        for p, dist in data.sensitivity
    )
    risk_labels = [f"{tv:.0%}" for tv, _ in data.risk_sweep]
    risk_values = [dist.median - start for _, dist in data.risk_sweep]
    best_tv, best_dist = max(data.risk_sweep, key=lambda r: r[1].median)
    lowest_tv = min(tv for tv, _ in data.risk_sweep)
    if best_tv <= lowest_tv:
        risk_finding = (
            f"In this run the best setting is the lowest one tested "
            f"({best_tv:.0%} annualised), and the curve is falling all the way down to it. "
            f"That is itself a measurement: it says the edge this agent actually captures is "
            f"<em>smaller</em> than {best_tv:.0%}, so the growth-optimal risk level sits below "
            f"the bottom of the chart. Every step up the risk ladder from there is pure drag."
        )
    else:
        risk_finding = (
            f"In this run growth peaks at a {best_tv:.0%} volatility target "
            f"(median {_fmt_money(best_dist.median)}) and falls away on both sides — too little "
            f"risk leaves the edge unused, too much hands it back as drag."
        )
    risk_rows = "".join(
        f"<tr><td>{tv:.0%}{' &larr; best' if tv == best_tv else ''}</td>"
        f"<td>{_fmt_money(dist.median)}</td><td>{_fmt_money(dist.p05)}</td>"
        f"<td>{_fmt_money(dist.p95)}</td>"
        f"<td class='{'pos' if dist.prob_profit > 0.5 else 'neg'}'>{dist.prob_profit:.0%}</td>"
        f"<td>{dist.median_drawdown:.0%}</td></tr>"
        for tv, dist in data.risk_sweep
    )

    cmp_rows = "".join(
        f"<tr><td>{html.escape(name)}</td><td>{_fmt_money(dist.median)}</td>"
        f"<td>{_fmt_money(dist.p05)}</td><td>{_fmt_money(dist.p95)}</td>"
        f"<td class='{'pos' if dist.prob_profit > 0.5 else 'neg'}'>{dist.prob_profit:.0%}</td>"
        f"<td>{dist.prob_ruin:.0%}</td><td>{dist.median_drawdown:.0%}</td></tr>"
        for name, dist in data.comparison
    )

    keep = {"entry", "exit", "liquidation", "pyramid", "halt", "pause", "daily"}
    picks = [j for j in r.journal if j.kind in keep]
    if len(picks) > 26:
        stride = len(picks) / 26
        picks = [picks[int(i * stride)] for i in range(26)]
    journal = "".join(
        f"<li class='{html.escape(j.kind)}'><span class='t'>{html.escape(j.time)}</span> "
        f"{html.escape(j.text)}</li>"
        for j in picks
    )

    where_labels = ["Gross trading P&L", "Fees", "Funding", "Net result"]
    gross = sum(t.gross_pnl for t in r.trades)
    where_values = [gross, -s.fees_paid, -s.funding_paid, s.final_equity - start]

    body = f"""
<div class="wrap">
  <h1>Claude trades $1,000 for 30 days, flat out</h1>
  <p class="lede">An autonomous agent running an ultra-aggressive leveraged strategy on
  simulated 24/7 crypto perpetual futures — 288 decisions a day, every day, for a month.</p>

  <div class="banner">
    <div>
      <strong>This is a simulation. No money, real or otherwise, was ever at risk.</strong>
      <p>Prices are synthetic, generated by the model described at the bottom of this page.
      Nothing here is a forecast, a backtest of real history, or investment advice. The
      numbers describe the behaviour of a model, not of any real market.</p>
    </div>
  </div>

  <h2>What happened on this path</h2>
  <p class="muted">Seed {cfg.seed} · preset <span class="journal">{html.escape(cfg.risk.name)}</span>
  · predictability dial {cfg.predictability:.2f}</p>
  <div class="tiles">{tiles}</div>
  {"<p><strong>The run was halted early:</strong> " + html.escape(r.halt_reason) + ".</p>" if r.halted_at is not None else ""}

  <h2>Equity curve</h2>
  <p>Account value every 5 minutes, all 8,640 decision points.</p>
  {line_chart(r.equity_curve, baseline=start, label="Account equity", chart_id="equity")}

  <h2>Drawdown</h2>
  <p>How far below the running high-water mark the account sat, as a percentage.</p>
  {line_chart(dd_curve, baseline=0.0, label="Drawdown", color="var(--series-4)",
                chart_id="dd", value_fmt=_fmt_pct)}

  <h2>Where the money actually went</h2>
  <p>Gross trading result, then what the venue took out of it.</p>
  {bar_chart(where_labels, where_values, chart_id="costs")}

  <h2>One path is a sample of size one</h2>
  <p>The same agent, the same settings, run over {d.n} independently generated months.
  This is the distribution the single run above was drawn from — and it is the only
  honest way to read a leveraged strategy's result.</p>
  <div class="tiles">{mc_tiles}</div>
  {histogram(data.path_equities, start=start, chart_id="mc")}

  <h2>How much of this is the strategy, and how much is the assumption?</h2>
  <p>The market model has one dial: <em>predictability</em>, the annualised Sharpe ratio a
  well-matched trend filter could extract before costs. At <strong>0.00</strong> the market is
  efficient and no technical strategy can win. Everything above that is an assumption about
  how much exploitable structure exists — an assumption no one can verify for you.</p>
  <div class="scroll"><table>
    <tr><th>Predictability</th><th>Median</th><th>5th pct</th><th>95th pct</th>
        <th>P(profit)</th><th>P(ruin)</th></tr>
    {sens_rows}
  </table></div>

  <h2>Why maximum aggression cannot be the answer</h2>
  <p>This is the part of the brief that does not survive contact with the arithmetic.
  An account running at leverage <em>L</em> on an edge worth Sharpe <em>S</em>, in a market
  of volatility <em>v</em>, grows at</p>
  <p style="font-family:var(--mono);color:var(--text-primary);text-align:center;margin:14px 0">
    growth &nbsp;=&nbsp; L&middot;S&middot;v &nbsp;&minus;&nbsp; &frac12;(L&middot;v)&sup2;
    &nbsp;&minus;&nbsp; costs</p>
  <p>The reward from leverage is <em>linear</em>. The volatility drag against it is
  <em>quadratic</em>. So growth peaks where account volatility equals the edge actually being
  captured — the Kelly point — and crosses back below zero at roughly twice it. Past that
  line, more aggression loses money <strong>no matter how good the signal is</strong>. It is
  not a question of nerve or discipline; it is a property of compounding.</p>
  <p>Below: the same agent and the same markets, run at five different volatility targets.
  Bars show the median 30-day profit or loss against the $1,000 starting stake.
  {risk_finding}</p>
  {bar_chart(risk_labels, risk_values, chart_id='risk')}
  <div class="scroll"><table>
    <tr><th>Annualised volatility target</th><th>Median</th><th>5th pct</th><th>95th pct</th>
        <th>P(profit)</th><th>Median DD</th></tr>
    {risk_rows}
  </table></div>

  <h2>Strategy by strategy</h2>
  <p>Identical signals where shared, identical markets throughout. The only differences are
  how positions are sized and how much risk is taken.</p>
  <div class="scroll"><table>
    <tr><th>Strategy</th><th>Median</th><th>5th pct</th><th>95th pct</th>
        <th>P(profit)</th><th>P(ruin)</th><th>Median DD</th></tr>
    {cmp_rows}
  </table></div>

  <h2>Result by market</h2>
  {bar_chart(list(data.per_asset), list(data.per_asset.values()), chart_id="assets")}

  <h2>Trade statistics</h2>
  <div class="scroll"><table>
    <tr><th>Metric</th><th>Value</th><th>Metric</th><th>Value</th></tr>
    <tr><td>Trades</td><td>{s.trades:,}</td><td>Win rate</td><td>{s.win_rate:.1%}</td></tr>
    <tr><td>Average win</td><td>{_fmt_money(s.avg_win)}</td><td>Average loss</td><td>{_fmt_money(s.avg_loss)}</td></tr>
    <tr><td>Best trade</td><td>{_fmt_money(s.best_trade)}</td><td>Worst trade</td><td>{_fmt_money(s.worst_trade)}</td></tr>
    <tr><td>Profit factor</td><td>{s.profit_factor:.2f}</td><td>Expectancy</td><td>{s.expectancy_r:+.3f} R</td></tr>
    <tr><td>Average leverage</td><td>{s.avg_leverage:.1f}x</td><td>Peak leverage</td><td>{s.peak_leverage:.1f}x</td></tr>
    <tr><td>Time in market</td><td>{s.time_in_market:.0%}</td><td>Notional traded</td><td>{_fmt_money(s.turnover_notional)}</td></tr>
    <tr><td>Fees</td><td>{_fmt_money(s.fees_paid)}</td><td>Funding</td><td>{_fmt_money(s.funding_paid)}</td></tr>
    <tr><td>Annualised Sharpe</td><td>{s.sharpe:.2f}</td><td>Annualised Sortino</td><td>{s.sortino:.2f}</td></tr>
  </table></div>
  <p class="muted">Sharpe and Sortino are annualised from 5-minute returns over a single
  month. The standard error on a one-month estimate is large; read them as shape, not
  as measurement.</p>

  <h2>The agent's journal</h2>
  <p>A sample of the decisions, in the agent's own words.</p>
  <ul class="journal">{journal}</ul>

  <h2>Method, and what would make this wrong</h2>
  <h3>What is simulated</h3>
  <ul class="plain">
    <li>Four synthetic perpetual-futures markets on 5-minute bars, 24/7, for {cfg.days} days.</li>
    <li>Prices follow a regime-switching jump diffusion. Regimes change volatility only,
        never drift, so that the <em>predictability&nbsp;=&nbsp;0</em> setting is a genuine null.</li>
    <li>Intrabar highs and lows are sampled from the exact Brownian-bridge distribution, so
        the trading range stays consistent with close-to-close volatility. An invented wick
        model would hand every stop-based strategy a free loss.</li>
    <li>Isolated margin, taker fees, half-spread, square-root market impact, 8-hourly
        funding, and liquidation checked against intrabar extremes.</li>
    <li>Within a bar, the adverse extreme is assumed to be touched before the favourable
        one, and a gap through a trigger fills at the open.</li>
  </ul>
  <h3>What is assumed, and is not verified</h3>
  <ul class="plain">
    <li>Every fee, volatility and funding parameter is an order-of-magnitude estimate, not a
        measurement from a primary source. They are plausible; they are not verified.</li>
    <li>The predictability dial is the load-bearing assumption. No claim is made about which
        value matches any real market.</li>
    <li>The agent is always able to trade at the modelled cost. Real venues have outages,
        rate limits, rejected orders, and much worse fills in exactly the conditions where
        this agent wants to trade most.</li>
    <li>There is no tax, no borrow limit, no exchange counterparty risk, and no bug in the
        agent's own code — three of which are real risks in live trading.</li>
  </ul>

  <footer>
    <p class="muted">Generated {html.escape(data.generated)} ·
    Simulated results from synthetic data · Not investment advice ·
    No order was ever placed anywhere.</p>
  </footer>
</div>
"""
    if not standalone:
        return (f"<title>Claude's 30-Day Paper Trading Run</title>\n{FONT_LINK}\n"
                f"<style>{CSS}</style>\n{body}\n<script>{JS}</script>")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claude's 30-Day Paper Trading Run</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
{FONT_LINK}
<style>{CSS}</style>
</head>
<body>
{body}
<script>{JS}</script>
</body>
</html>
"""
