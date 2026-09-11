#!/usr/bin/env python3
"""Run the paper account against real market data, one update at a time.

    python3 live_trade.py --check                      # can we reach the venue?
    python3 live_trade.py --venue binance --update     # fetch, decide, save
    python3 live_trade.py --status                     # read state, no network
    python3 live_trade.py --email                      # render the daily email

The account lives in a JSON state file that survives between runs, so this
can be invoked from cron, a CI job, or a scheduled agent session and simply
pick up where it left off.

It is still paper trading. Prices are real; the money is not. No order is
ever sent to any venue, and the code has no capacity to place one — there is
no API key, no signing, and no authenticated endpoint anywhere in it.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from dataclasses import replace

from paper_trader.agent import AutonomousTrader
from paper_trader.config import PRESETS, SimConfig
from paper_trader.email_report import html_body, plain_text, subject
from paper_trader.indicators import SymbolState
from paper_trader.live import (MAX_BARS_PER_CALL, VENUES, LiveDataUnavailable,
                               build_live_market, check_connection, fetch_bars)
from paper_trader.state import LiveState, load, save

DEFAULT_STATE = "live_state.json"


def warmup_bars(preset_name: str) -> int:
    """How many bars the indicators need before the agent may act."""
    risk = PRESETS[preset_name]
    probe = SymbolState(risk.timescale)
    return max(probe.slow_n, probe.channel_high.period, probe.rets.period) + 10


def cmd_check(args) -> int:
    names = [args.venue] if args.venue else sorted(VENUES)
    worst = 0
    for name in names:
        r = check_connection(name, args.symbols[0] if args.symbols else None,
                             base_url=args.base_url)
        print(f"\n  venue   {r['venue']}")
        print(f"  symbol  {r['symbol']}")
        print(f"  url     {r['url']}")
        if r["ok"]:
            print(f"  RESULT  OK — {r['bars']} bars, latest close {r['latest_close']:,.4f}")
        else:
            worst = 1
            print(f"  RESULT  FAILED\n          {r['error']}")
    print()
    if worst:
        print("  No venue responded. On a managed network this is usually the egress")
        print("  allowlist, not the exchange — the host has to be permitted first.")
    return worst


def cmd_status(args) -> int:
    state = load(args.state)
    if state is None:
        print(f"No state at {args.state}. Run --update first.")
        return 1
    print(plain_text(state))
    return 0


def cmd_email(args) -> int:
    state = load(args.state)
    if state is None:
        print(f"No state at {args.state}. Run --update first.")
        return 1
    payload = {"to": args.to, "subject": subject(state),
               "text": plain_text(state), "html": html_body(state)}
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print(f"To:      {payload['to']}")
        print(f"Subject: {payload['subject']}")
        print()
        print(payload["text"])
    return 0


def cmd_update(args) -> int:
    state = load(args.state)
    if state is None:
        symbols = args.symbols or list(VENUES[args.venue].example_symbols)
        state = LiveState(
            venue=args.venue, symbols=symbols, interval_minutes=args.interval,
            preset=args.preset, starting_cash=args.cash, cash=args.cash,
            peak_equity=args.cash, last_equity=args.cash,
        )
        print(f"  Opened a new paper account with ${args.cash:,.2f} on "
              f"{args.venue}: {', '.join(symbols)}")
    else:
        print(f"  Resuming account from {args.state} "
              f"(last updated {state.updated_at})")

    cfg = SimConfig(
        predictability=0.0,   # irrelevant for live data; no market is generated
        risk=replace(PRESETS[state.preset], starting_cash=state.starting_cash),
    )

    # Size the fetch to actually cover the gap since the last run. A fixed
    # window looks fine when you test it minutes apart and silently skips
    # bars once the job runs daily — the account would then trade a handful
    # of bars and ignore the rest of the day.
    warm = warmup_bars(state.preset)
    gap_bars = 0
    if state.last_aligned_ts > 0:
        now_ms = int(dt.datetime.now(dt.timezone.utc).timestamp() * 1000)
        gap_ms = max(0, now_ms - state.last_aligned_ts)
        gap_bars = int(gap_ms / (state.interval_minutes * 60_000)) + 2
    need = warm + gap_bars + args.extra_bars

    cap = MAX_BARS_PER_CALL.get(state.venue, 1000)
    if need > cap:
        print(f"  WARNING: covering the gap since the last run needs ~{need} bars but "
              f"{state.venue} returns at most {cap} per call.")
        print(f"           Bars older than that window will be skipped. Run more often, "
              f"or use a longer --interval.")
        need = cap
    elif gap_bars:
        print(f"  Fetching {need} bars ({warm} warmup + ~{gap_bars} since the last run).")

    try:
        series = {
            sym: fetch_bars(state.venue, sym, state.interval_minutes, limit=need,
                            base_url=args.base_url)
            for sym in state.symbols
        }
        market = build_live_market(series, state.interval_minutes, args.funding_rate)
    except (LiveDataUnavailable, ValueError) as exc:
        state.last_run_status = "live data unavailable"
        state.last_run_error = str(exc)
        state.updated_at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        save(args.state, state)
        print(f"\n  COULD NOT UPDATE: {exc}")
        print("  State left untouched apart from recording the failure, so the")
        print("  next email will say the number is stale instead of pretending.")
        return 2

    stamps = market.timestamps
    if state.last_aligned_ts <= 0:
        # A brand-new account starts trading from now, not by replaying the
        # fetched history as though those trades had happened.
        act_from = len(stamps) - 1
        print(f"  Warmed indicators on {act_from} historical bars; "
              f"trading starts from the latest completed bar.")
    else:
        act_from = next((i for i, t in enumerate(stamps) if t > state.last_aligned_ts),
                        len(stamps))
        if act_from >= len(stamps):
            print(f"  No completed bars newer than "
                  f"{dt.datetime.fromtimestamp(state.last_aligned_ts / 1000, dt.timezone.utc)}. "
                  f"Nothing to do.")
            state.last_run_status = "ok"
            state.last_run_error = ""
            save(args.state, state)
            return 0
        print(f"  {len(stamps) - act_from} new bar(s) to process.")

    if act_from < warmup_bars(state.preset):
        print(f"  NOTE: only {act_from} warmup bars available; the agent will hold "
              f"off until its indicators are ready.")

    account = state.to_account(cfg.venue)
    prices_now = {s: market.bars[s][act_from - 1].close if act_from > 0
                  else market.bars[s][0].close for s in market.symbols}
    state.roll_day_anchor(account.equity(prices_now))

    trader = AutonomousTrader(
        cfg, market, account=account, act_from=act_from,
        close_at_end=False, daily_anchor=state.day_anchor_equity,
    )
    trader.peak_equity = max(state.peak_equity, account.equity(prices_now))
    result = trader.run()

    final_prices = {s: market.bars[s][-1].close for s in market.symbols}
    equity = account.equity(final_prices)
    state.absorb(account, equity)
    state.peak_equity = max(state.peak_equity, trader.peak_equity)
    state.last_aligned_ts = stamps[-1]
    state.last_bar_ts = {s: stamps[-1] for s in market.symbols}
    state.data_source = "live"
    state.last_run_status = "ok"
    state.last_run_error = ""
    state.mark_day(equity)
    state.equity_history.append([state.updated_at, round(equity, 4)])
    state.equity_history = state.equity_history[-2000:]
    for entry in result.journal:
        if entry.kind in {"entry", "exit", "liquidation", "halt", "pause", "pyramid"}:
            state.journal.append(f"{state.updated_at} {entry.kind} {entry.symbol}: {entry.text}")
    state.journal = state.journal[-400:]
    save(args.state, state)

    print(f"\n  Equity          ${equity:,.2f} "
          f"({equity / state.starting_cash - 1:+.2%} since inception)")
    print(f"  Cash            ${account.cash:,.2f}")
    print(f"  Open positions  {len(account.positions)}")
    print(f"  Closed trades   {len(account.trades)}")
    print(f"  Drawdown        {state.drawdown:.1%} from a ${state.peak_equity:,.2f} peak")
    print(f"  State saved to  {args.state}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="test venue connectivity")
    mode.add_argument("--update", action="store_true", help="fetch data and advance the account")
    mode.add_argument("--status", action="store_true", help="print saved state, no network")
    mode.add_argument("--email", action="store_true", help="render the daily email")

    ap.add_argument("--venue", choices=sorted(VENUES), default="binance")
    ap.add_argument("--symbols", nargs="*", default=None)
    ap.add_argument("--interval", type=int, default=5, help="bar interval in minutes")
    ap.add_argument("--preset", choices=sorted(PRESETS), default="ultra-aggressive")
    ap.add_argument("--cash", type=float, default=1_000.0)
    ap.add_argument("--state", default=DEFAULT_STATE)
    ap.add_argument("--extra-bars", type=int, default=120,
                    help="bars fetched beyond the indicator warmup requirement")
    ap.add_argument("--base-url", default=None,
                    help="override the venue base URL (for a mirror, or for tests)")
    ap.add_argument("--funding-rate", type=float, default=0.0,
                    help="flat 8-hourly funding to charge; spot candles have none")
    ap.add_argument("--to", default="", help="recipient shown in --email output")
    ap.add_argument("--json", action="store_true", help="machine-readable --email output")
    args = ap.parse_args(argv)

    print("\n" + "=" * 72)
    print("  PAPER TRADING — simulated account, real prices, no orders placed")
    print("=" * 72)

    if args.check:
        return cmd_check(args)
    if args.status:
        return cmd_status(args)
    if args.email:
        return cmd_email(args)
    return cmd_update(args)


if __name__ == "__main__":
    sys.exit(main())
