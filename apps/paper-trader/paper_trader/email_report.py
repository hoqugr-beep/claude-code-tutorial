"""The daily balance email.

Two rules shape this file:

* **Never present stale numbers as current.** If the last run could not
  fetch data, the email leads with that, and every figure below is labelled
  as of its actual timestamp. A balance email that silently repeats
  yesterday's number is worse than one that admits it is stuck.
* **Never let a simulation read as a real account.** Subject line and body
  both say so.
"""

from __future__ import annotations

import datetime as dt
import html

from .state import LiveState


def _money(x: float) -> str:
    return f"${x:,.2f}"


def _pct(x: float) -> str:
    return f"{x:+.2%}"


def _age(iso: str) -> str:
    try:
        when = dt.datetime.fromisoformat(iso)
    except ValueError:
        return "unknown"
    if when.tzinfo is None:
        when = when.replace(tzinfo=dt.timezone.utc)
    delta = dt.datetime.now(dt.timezone.utc) - when
    hours = delta.total_seconds() / 3600
    if hours < 1:
        return f"{delta.total_seconds() / 60:.0f} minutes ago"
    if hours < 48:
        return f"{hours:.0f} hours ago"
    return f"{hours / 24:.0f} days ago"


def subject(state: LiveState) -> str:
    if state.last_run_status != "ok":
        return f"[SIM] Paper trading — no update ({state.last_run_status})"
    change = state.change_since_previous_mark()
    tail = f" ({_pct(change[1])} since last mark)" if change else ""
    return f"[SIM] Paper trading balance: {_money(state.last_equity)}{tail}"


def _recent_trades(state: LiveState, hours: int = 24) -> list[dict]:
    # Trades carry bar indices rather than wall-clock times, so "recent" is
    # taken as the tail of the trade log rather than pretending to a
    # precision the record does not have.
    return state.trades[-8:]


def plain_text(state: LiveState) -> str:
    lines: list[str] = []
    add = lines.append

    add("PAPER TRADING — SIMULATED ACCOUNT")
    add("No real money. No orders are placed anywhere.")
    add("")

    if state.last_run_status != "ok":
        add("!! THIS IS NOT A FRESH NUMBER !!")
        add(f"The last update did not succeed: {state.last_run_status}")
        if state.last_run_error:
            add(f"Reason: {state.last_run_error}")
        add("Everything below is the last good state, not the current market.")
        add("")

    add(f"Balance            {_money(state.last_equity)}")
    add(f"Started with       {_money(state.starting_cash)}")
    add(f"Total return       {_pct(state.total_return)}")
    change = state.change_since_previous_mark()
    if change:
        add(f"Since last mark    {_money(change[0])} ({_pct(change[1])})")
    add(f"Peak equity        {_money(state.peak_equity)}")
    add(f"Drawdown from peak {state.drawdown:.1%}")
    add("")
    add(f"Cash               {_money(state.cash)}")
    add(f"Open positions     {len(state.positions)}")
    add(f"Closed trades      {len(state.trades)}")
    add(f"Fees paid          {_money(state.fees_total)}")
    add(f"Liquidations       {state.liquidations}")
    add("")

    if state.positions:
        add("OPEN POSITIONS")
        for p in state.positions:
            side = "LONG " if p.get("side", 1) > 0 else "SHORT"
            add(f"  {side} {p.get('symbol','?'):<12} qty {p.get('qty',0):.6g} "
                f"@ {p.get('entry_price',0):,.4f}  "
                f"margin {_money(p.get('margin',0.0))}  "
                f"{p.get('leverage',0):.1f}x")
        add("")

    recent = _recent_trades(state)
    if recent:
        add("MOST RECENT CLOSED TRADES")
        for t in recent:
            side = "long " if t.get("side", 1) > 0 else "short"
            add(f"  {side} {t.get('symbol','?'):<12} "
                f"{_money(t.get('net_pnl', 0.0)):>12}  "
                f"({t.get('r_multiple', 0.0):+.2f}R, {t.get('reason','')})")
        add("")

    add("DATA")
    add(f"  Source           {state.data_source} ({state.venue})")
    add(f"  Symbols          {', '.join(state.symbols) or 'none'}")
    add(f"  Bar interval     {state.interval_minutes} minutes")
    add(f"  Risk preset      {state.preset}")
    add(f"  State updated    {state.updated_at} ({_age(state.updated_at)})")
    add("")
    add("This is a simulation running on a paper account. The strategy it runs")
    add("lost money on the large majority of simulated months. Do not read this")
    add("as advice, a forecast, or a track record.")
    return "\n".join(lines)


def html_body(state: LiveState) -> str:
    good = state.last_run_status == "ok"
    up = state.total_return >= 0
    change = state.change_since_previous_mark()

    def row(k: str, v: str, colour: str = "") -> str:
        style = f" style='color:{colour}'" if colour else ""
        return (f"<tr><td style='padding:4px 14px 4px 0;color:#6b6a66'>{html.escape(k)}</td>"
                f"<td style='padding:4px 0;font-family:ui-monospace,Menlo,monospace;"
                f"text-align:right'{style}>{html.escape(v)}</td></tr>")

    warn = ""
    if not good:
        warn = (
            "<div style='border-left:4px solid #c07000;background:#fff8ec;"
            "padding:10px 14px;margin:0 0 16px'>"
            "<strong>This is not a fresh number.</strong><br>"
            f"The last update failed: {html.escape(state.last_run_status)}."
            + (f"<br><span style='color:#6b6a66'>{html.escape(state.last_run_error)}</span>"
               if state.last_run_error else "")
            + "<br>Everything below is the last good state.</div>"
        )

    positions = ""
    if state.positions:
        rows = "".join(
            f"<tr><td style='padding:3px 12px 3px 0'>"
            f"{'LONG' if p.get('side',1) > 0 else 'SHORT'} {html.escape(str(p.get('symbol','?')))}</td>"
            f"<td style='padding:3px 12px 3px 0;text-align:right;"
            f"font-family:ui-monospace,Menlo,monospace'>{p.get('qty',0):.6g}</td>"
            f"<td style='padding:3px 0;text-align:right;"
            f"font-family:ui-monospace,Menlo,monospace'>{p.get('entry_price',0):,.4f}</td></tr>"
            for p in state.positions
        )
        positions = (
            "<h3 style='font-size:13px;text-transform:uppercase;letter-spacing:.06em;"
            "color:#6b6a66;margin:22px 0 6px'>Open positions</h3>"
            f"<table style='border-collapse:collapse;font-size:13px'>{rows}</table>"
        )

    return f"""<div style="font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;
 max-width:560px;color:#1a1a19;line-height:1.55">
  <div style="font-size:11px;text-transform:uppercase;letter-spacing:.09em;color:#8a8880">
    Simulated paper account &middot; no real money
  </div>
  <div style="font-size:34px;font-weight:600;margin:6px 0 2px;
       font-family:ui-monospace,Menlo,monospace;color:{'#1a7f5a' if up else '#c0392b'}">
    {html.escape(_money(state.last_equity))}
  </div>
  <div style="color:#6b6a66;font-size:14px;margin-bottom:18px">
    {html.escape(_pct(state.total_return))} since inception
    {('&middot; ' + html.escape(_pct(change[1])) + ' since last mark') if change else ''}
  </div>
  {warn}
  <table style="border-collapse:collapse;font-size:13.5px">
    {row('Started with', _money(state.starting_cash))}
    {row('Cash', _money(state.cash))}
    {row('Peak equity', _money(state.peak_equity))}
    {row('Drawdown from peak', f'{state.drawdown:.1%}', '#c0392b' if state.drawdown > 0.2 else '')}
    {row('Open positions', str(len(state.positions)))}
    {row('Closed trades', str(len(state.trades)))}
    {row('Fees paid', _money(state.fees_total))}
    {row('Liquidations', str(state.liquidations))}
  </table>
  {positions}
  <h3 style="font-size:13px;text-transform:uppercase;letter-spacing:.06em;
      color:#6b6a66;margin:22px 0 6px">Data</h3>
  <table style="border-collapse:collapse;font-size:13.5px">
    {row('Source', f'{state.data_source} ({state.venue})')}
    {row('Symbols', ', '.join(state.symbols) or 'none')}
    {row('Interval', f'{state.interval_minutes} min')}
    {row('Preset', state.preset)}
    {row('Updated', _age(state.updated_at))}
  </table>
  <p style="color:#8a8880;font-size:12px;margin-top:22px;border-top:1px solid #e4e2dc;
     padding-top:12px">
    Simulation on a paper account. The strategy this runs lost money on the large
    majority of simulated months. Not advice, not a forecast, not a track record.
  </p>
</div>"""
