"""The autonomous agent loop: 24/7, one decision cycle every 5 minutes.

The agent never sleeps — crypto perpetuals trade continuously, so the loop
runs 288 cycles a day for the whole simulated month.  Every cycle it:

1. updates its view of each market,
2. settles funding when an 8-hour boundary passes,
3. manages open risk (liquidation, stops, trailing stops, targets, pyramids),
4. checks its kill switches,
5. and only then looks for new positions.

Risk management runs before new entries on purpose: an agent that opens
before it protects is one bad bar from an empty account.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .config import BARS_PER_DAY, FUNDING_INTERVAL_BARS, RiskConfig, SimConfig
from .exchange import Account, Position, Trade
from .indicators import SymbolState
from .market import Bar, Market
from .strategy import FLIP_THRESHOLD, Signal, conviction, evaluate, leverage_for_stop

TIME_STOP_MIN_R = 0.25                 # a trade is "working" past this much R
RUIN_EQUITY = 25.0                     # below this, no order clears min notional


def clock(bar: int) -> str:
    day, rem = divmod(bar, BARS_PER_DAY)
    minutes = rem * 5
    return f"D{day + 1:02d} {minutes // 60:02d}:{minutes % 60:02d}"


@dataclass
class JournalEntry:
    bar: int
    time: str
    kind: str
    symbol: str
    equity: float
    text: str


@dataclass
class RunResult:
    config: SimConfig
    equity_curve: list[float]
    cash_curve: list[float]
    leverage_curve: list[float]
    daily_equity: list[float]
    trades: list[Trade]
    journal: list[JournalEntry]
    account: Account
    market: Market
    halted_at: int | None = None
    halt_reason: str = ""
    pause_days: int = 0

    @property
    def final_equity(self) -> float:
        return self.equity_curve[-1]

    @property
    def total_return(self) -> float:
        return self.final_equity / self.config.risk.starting_cash - 1.0


class AutonomousTrader:
    """The decision loop, driven identically by the backtest and by live data.

    `account`, `act_from` and `close_at_end` are what let a live run reuse
    this class unchanged: it restores an existing account, replays earlier
    bars to warm the indicators *without* trading them, acts only on bars it
    has not seen before, and leaves open positions open for the next run.
    Sharing one code path between simulation and live is the point — a
    separate "live version" of a strategy is a separate set of bugs.
    """

    def __init__(
        self,
        config: SimConfig,
        market: Market,
        account: Account | None = None,
        act_from: int = 0,
        close_at_end: bool = True,
        daily_anchor: float | None = None,
    ) -> None:
        self.cfg = config
        self.risk: RiskConfig = config.risk
        self.market = market
        self.act_from = act_from
        self.close_at_end = close_at_end
        # When set, the daily loss limit is measured from this equity instead
        # of from a bar-counted day boundary (see LiveState.roll_day_anchor).
        self.daily_anchor = daily_anchor
        self.account = account if account is not None else Account(
            cash=config.risk.starting_cash, venue=config.venue
        )
        self.state = {
            s: SymbolState(config.risk.timescale) for s in market.symbols
        }
        self.cooldown: dict[str, int] = {s: -10_000 for s in market.symbols}
        self.journal: list[JournalEntry] = []
        self.equity_curve: list[float] = []
        self.cash_curve: list[float] = []
        self.leverage_curve: list[float] = []
        self.daily_equity: list[float] = []
        self.peak_equity = max(config.risk.starting_cash, self.account.cash)
        self.day_start_equity = config.risk.starting_cash
        self.paused_day: int | None = None
        self.pause_days = 0
        self.halted_at: int | None = None
        self.halt_reason = ""

    # ---- journal ---------------------------------------------------------

    def log(self, bar: int, kind: str, symbol: str, equity: float, text: str) -> None:
        self.journal.append(JournalEntry(bar, clock(bar), kind, symbol, equity, text))

    # ---- main loop -------------------------------------------------------

    def run(self) -> RunResult:
        m = self.market
        n = m.n_bars
        if self.act_from == 0:
            self.log(0, "start", "-", self.account.cash,
                     f"Session opened with ${self.account.cash:,.2f}. Preset: "
                     f"{self.risk.name}; universe: {', '.join(m.symbols)}.")

        for i in range(n):
            bars = {s: m.bars[s][i] for s in m.symbols}
            feats = {
                s: self.state[s].update(b.open, b.high, b.low, b.close, b.volume_usd)
                for s, b in bars.items()
            }
            prices = {s: b.close for s, b in bars.items()}

            # Bars before `act_from` are history: they warm the indicators up
            # but must not trade, or a live run would re-trade its own past.
            if i < self.act_from:
                continue

            day = i // BARS_PER_DAY
            if self.daily_anchor is not None:
                self.day_start_equity = self.daily_anchor
            elif i % BARS_PER_DAY == 0:
                self.day_start_equity = self.account.equity(prices)
            if i % BARS_PER_DAY == 0:
                if self.paused_day is not None and day > self.paused_day:
                    self.paused_day = None
                    self.log(i, "resume", "-", self.day_start_equity,
                             "New trading day: daily loss limit reset, resuming.")

            if i > 0 and i % FUNDING_INTERVAL_BARS == 0 and self.account.positions:
                rates = {s: m.funding[s][i] for s in m.symbols}
                paid = self.account.settle_funding(rates, prices)
                if abs(paid) > 0.01:
                    self.log(i, "funding", "-", self.account.equity(prices),
                             f"Funding settled: {'paid' if paid > 0 else 'received'} "
                             f"${abs(paid):,.2f} across {len(self.account.positions)} position(s).")

            self._manage_positions(i, bars, feats, prices)

            equity = self.account.equity(prices)
            self.peak_equity = max(self.peak_equity, equity)

            if self.halted_at is None:
                self._check_kill_switches(i, day, equity, prices)

            if (
                self.halted_at is None
                and self.paused_day is None
                and i % self.risk.decision_every == 0
            ):
                self._seek_entries(i, bars, feats, prices)

            equity = self.account.equity(prices)
            self.equity_curve.append(equity)
            self.cash_curve.append(self.account.cash)
            self.leverage_curve.append(
                self.account.gross_notional(prices) / equity if equity > 0 else 0.0
            )
            if (i + 1) % BARS_PER_DAY == 0:
                self.daily_equity.append(equity)
                self.log(i, "daily", "-", equity,
                         f"End of day {day + 1}: equity ${equity:,.2f} "
                         f"({equity / self.risk.starting_cash - 1:+.1%} on the month), "
                         f"{len(self.account.positions)} open, "
                         f"{len(self.account.trades)} trades closed to date.")

        last = {s: m.bars[s][n - 1].close for s in m.symbols}
        if self.close_at_end:
            for sym in list(self.account.positions):
                self.account.close_position(
                    sym, last[sym], n - 1, "end-of-simulation", m.spec[sym].adv_usd
                )
        final = self.account.equity(last)
        if self.equity_curve:
            self.equity_curve[-1] = final
        verb = "Simulation complete" if self.close_at_end else "Session paused, positions held"
        self.log(n - 1, "end", "-", final,
                 f"{verb}. Equity ${final:,.2f} "
                 f"({final / self.risk.starting_cash - 1:+.1%}).")

        return RunResult(
            config=self.cfg,
            equity_curve=self.equity_curve,
            cash_curve=self.cash_curve,
            leverage_curve=self.leverage_curve,
            daily_equity=self.daily_equity,
            trades=self.account.trades,
            journal=self.journal,
            account=self.account,
            market=self.market,
            halted_at=self.halted_at,
            halt_reason=self.halt_reason,
            pause_days=self.pause_days,
        )

    # ---- risk management -------------------------------------------------

    def _intrabar_exit(self, pos: Position, bar: Bar) -> tuple[str, float] | None:
        """Did the bar take this position out, and at what price?

        Conservative convention: the adverse extreme is assumed to be touched
        before the favourable one, and a gap through a trigger fills at the
        open rather than at the trigger.
        """
        mm = self.cfg.venue.maintenance_margin
        liq = pos.liquidation_price(mm)

        if pos.side > 0:
            # Whichever trigger is higher is hit first on the way down.
            adverse, kind = (liq, "liquidated") if liq >= pos.stop else (pos.stop, "stop")
            if bar.open <= adverse:
                return kind, bar.open
            if bar.low <= adverse:
                return kind, adverse
            if pos.take_profit and bar.high >= pos.take_profit:
                return "take-profit", max(pos.take_profit, bar.open)
        else:
            adverse, kind = (liq, "liquidated") if liq <= pos.stop else (pos.stop, "stop")
            if bar.open >= adverse:
                return kind, bar.open
            if bar.high >= adverse:
                return kind, adverse
            if pos.take_profit and bar.low <= pos.take_profit:
                return "take-profit", min(pos.take_profit, bar.open)
        return None

    def _manage_positions(self, i: int, bars, feats, prices) -> None:
        acct = self.account
        for sym in list(acct.positions):
            pos = acct.positions[sym]
            bar, f = bars[sym], feats[sym]
            adv = self.market.spec[sym].adv_usd

            hit = self._intrabar_exit(pos, bar)
            if hit:
                kind, price = hit
                if kind == "liquidated":
                    t = acct.liquidate(sym, price, i)
                    self.log(i, "liquidation", sym, acct.equity(prices),
                             f"LIQUIDATED {'long' if pos.side > 0 else 'short'} {sym} at "
                             f"{price:,.4f}. Margin gone: ${-t.net_pnl:,.2f} "
                             f"({t.r_multiple:+.2f}R). Leverage cuts both ways.")
                else:
                    t = acct.close_position(sym, price, i, kind, adv, override_price=price)
                    self.log(i, "exit", sym, acct.equity(prices),
                             f"{kind.replace('-', ' ').title()} on {sym} at {price:,.4f}: "
                             f"{t.net_pnl:+,.2f} ({t.r_multiple:+.2f}R) after "
                             f"${t.fees:,.2f} fees.")
                self.cooldown[sym] = i
                continue

            price = bar.close
            # Trailing stop: ratchet once the trade is 1R onside.
            if pos.side > 0:
                pos.extreme_price = max(pos.extreme_price, bar.high)
                progress = (price - pos.entry_price) / pos.risk_per_unit if pos.risk_per_unit else 0.0
                if progress >= 1.0:
                    trail = pos.extreme_price - self.risk.trail_atr_mult * f.atr
                    pos.stop = max(pos.stop, trail, pos.entry_price)
            else:
                pos.extreme_price = min(pos.extreme_price, bar.low)
                progress = (pos.entry_price - price) / pos.risk_per_unit if pos.risk_per_unit else 0.0
                if progress >= 1.0:
                    trail = pos.extreme_price + self.risk.trail_atr_mult * f.atr
                    pos.stop = min(pos.stop, trail, pos.entry_price)

            sig = evaluate(f, self.market.funding[sym][i],
                           mom_bars=self.state[sym].mom_n,
                           trend_threshold=self.risk.trend_threshold)

            # Signal flip: the reason for the trade is gone, so is the trade.
            if sig.score * pos.side < 0 and abs(sig.score) >= FLIP_THRESHOLD:
                t = acct.close_position(sym, price, i, "signal-flip", adv)
                self.log(i, "exit", sym, acct.equity(prices),
                         f"Closed {sym} on signal flip ({sig.score:+.2f}): "
                         f"{t.net_pnl:+,.2f} ({t.r_multiple:+.2f}R). {sig.rationale}.")
                self.cooldown[sym] = i
                continue

            # Time stop: capital sitting in a trade that is going nowhere is
            # capital not compounding somewhere else.
            time_stop_bars = self.risk.time_stop_days * BARS_PER_DAY
            if i - pos.opened_bar > time_stop_bars and progress < TIME_STOP_MIN_R:
                t = acct.close_position(sym, price, i, "time-stop", adv)
                self.log(i, "exit", sym, acct.equity(prices),
                         f"Time stop on {sym} after "
                         f"{(i - pos.opened_bar) / BARS_PER_DAY:.1f} days at "
                         f"{progress:+.2f}R: {t.net_pnl:+,.2f}. Recycling the margin.")
                self.cooldown[sym] = i
                continue

            # Pyramid into strength.
            if (
                pos.pyramids < self.risk.max_pyramids
                and progress >= 1.0 + pos.pyramids
                and sig.score * pos.side > 0
                and abs(sig.score) >= self.risk.min_signal_strength
            ):
                add_qty = pos.qty * 0.5 / (pos.pyramids + 1)
                if acct.add_to_position(sym, add_qty, price, adv):
                    self.log(i, "pyramid", sym, acct.equity(prices),
                             f"Added to winning {sym} at {price:,.4f} "
                             f"(+{add_qty * price:,.0f} notional, add #{pos.pyramids}) "
                             f"— {progress:+.1f}R onside and signal still {sig.score:+.2f}.")

    def _check_kill_switches(self, i: int, day: int, equity: float, prices) -> None:
        def flatten(reason: str) -> None:
            for sym in list(self.account.positions):
                t = self.account.close_position(
                    sym, prices[sym], i, reason, self.market.spec[sym].adv_usd
                )
                self.cooldown[sym] = i

        if equity <= RUIN_EQUITY:
            flatten("ruin")
            self.halted_at = i
            self.halt_reason = "account effectively wiped out"
            self.log(i, "halt", "-", self.account.equity(prices),
                     f"HALT: equity ${equity:,.2f} is below the minimum viable "
                     f"order size. Nothing left to trade with.")
            return

        if equity <= self.peak_equity * (1.0 - self.risk.max_drawdown_stop):
            flatten("max-drawdown")
            self.halted_at = i
            self.halt_reason = (
                f"drawdown from peak exceeded {self.risk.max_drawdown_stop:.0%}"
            )
            self.log(i, "halt", "-", self.account.equity(prices),
                     f"HALT: drawdown of "
                     f"{1 - equity / self.peak_equity:.1%} from the ${self.peak_equity:,.2f} "
                     f"peak breached the {self.risk.max_drawdown_stop:.0%} circuit breaker. "
                     f"Trading stops for the rest of the month.")
            return

        if (
            self.paused_day is None
            and equity <= self.day_start_equity * (1.0 - self.risk.daily_loss_limit)
        ):
            flatten("daily-loss-limit")
            self.paused_day = day
            self.pause_days += 1
            self.log(i, "pause", "-", self.account.equity(prices),
                     f"Daily loss limit hit: down "
                     f"{1 - equity / self.day_start_equity:.1%} on day {day + 1}. "
                     f"Flat until tomorrow — the worst thing to do after a bad day "
                     f"is trade bigger to win it back.")

    # ---- entries ---------------------------------------------------------

    def _seek_entries(self, i: int, bars, feats, prices) -> None:
        acct = self.account
        equity = acct.equity(prices)
        if equity <= RUIN_EQUITY:
            return

        candidates: list[tuple[float, str, Signal]] = []
        for sym in self.market.symbols:
            if sym in acct.positions:
                continue
            if i - self.cooldown[sym] < self.risk.cooldown_bars:
                continue
            f = feats[sym]
            if not f.ready or f.atr <= 0:
                continue
            sig = evaluate(f, self.market.funding[sym][i],
                           mom_bars=self.state[sym].mom_n,
                           trend_threshold=self.risk.trend_threshold)
            if abs(sig.score) >= self.risk.min_signal_strength:
                if not self.risk.allow_shorts and sig.score < 0:
                    continue
                candidates.append((abs(sig.score), sym, sig))

        candidates.sort(reverse=True, key=lambda c: c[0])
        for _, sym, sig in candidates:
            if len(acct.positions) >= self.risk.max_positions:
                return
            self._try_open(i, sym, sig, feats[sym], prices, equity)

    def _try_open(self, i: int, sym: str, sig: Signal, f, prices, equity: float) -> None:
        acct = self.account
        cfg = self.cfg
        price = f.close
        side = sig.side
        adv = self.market.spec[sym].adv_usd

        stop_dist = self.risk.stop_atr_mult * f.atr
        if stop_dist <= 0:
            return

        # Cost filter: a trade whose unit of risk is small relative to the
        # round-trip cost of putting it on is a losing bet before the market
        # even moves.  This is what kills over-trading at high frequency.
        if self.risk.min_edge_ratio > 0:
            notional_guess = equity * self.risk.risk_per_trade * self.risk.max_leverage
            impact = cfg.venue.impact_coef * math.sqrt(max(notional_guess, 1.0) / adv)
            round_trip = 2.0 * (cfg.venue.taker_fee + cfg.venue.base_spread + impact)
            if stop_dist / price < self.risk.min_edge_ratio * round_trip:
                return

        size_mult = conviction(sig.score, self.risk.min_signal_strength)
        risk_amount = equity * self.risk.risk_per_trade * size_mult
        qty = risk_amount / stop_dist

        # Cap 1: strategy-level gross leverage across the whole book.
        gross_cap = equity * self.risk.max_leverage - acct.gross_notional(prices)
        if gross_cap <= cfg.venue.min_notional:
            return
        qty = min(qty, gross_cap / price)

        lev = leverage_for_stop(
            price, stop_dist, cfg.venue.maintenance_margin,
            cap=min(self.risk.max_leverage, cfg.venue.max_leverage),
        )

        # Cap 2: cash actually available after the untouchable reserve.
        spendable = acct.cash - equity * self.risk.reserve_cash
        if spendable <= 0:
            return
        per_unit_cost = price / lev * (1.0 + cfg.venue.taker_fee * lev)
        qty = min(qty, spendable / per_unit_cost)

        if qty * price < cfg.venue.min_notional:
            return

        stop = price - side * stop_dist
        take_profit = price + side * self.risk.take_profit_r * stop_dist
        pos = acct.open_position(
            sym, side, qty, price, i, stop, take_profit, lev, adv,
            note=f"{sig.mode}/{sig.score:+.2f}",
        )
        if pos is None:
            return

        self.log(i, "entry", sym, acct.equity(prices),
                 f"{'LONG' if side > 0 else 'SHORT'} {sym} — score {sig.score:+.2f} "
                 f"({sig.mode}). {sig.rationale}. Size {pos.qty * pos.entry_price:,.0f} "
                 f"notional at {lev:.1f}x, risking "
                 f"${pos.qty * pos.risk_per_unit:,.2f} "
                 f"({pos.qty * pos.risk_per_unit / equity:.1%} of equity) to a stop at "
                 f"{stop:,.4f}; liquidation {pos.liquidation_price(cfg.venue.maintenance_margin):,.4f}.")


def run_simulation(config: SimConfig, market: Market | None = None) -> RunResult:
    from .market import generate_market

    if market is None:
        market = generate_market(
            config.universe, config.bars, config.seed,
            config.predictability, config.venue,
        )
    return AutonomousTrader(config, market).run()
