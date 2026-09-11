"""A volatility-targeted trend filter — the strategy the market model says works.

The discrete strategy in `strategy.py` picks a direction, sizes to a stop, and
waits. That throws away most of a weak trend signal: it discretises a
continuous forecast into on/off, and a stop turns a shallow adverse move into a
realised loss even when the forecast has not changed.

This agent instead holds a *continuous* position proportional to its forecast,
scaled so the account runs at a target volatility, and rebalances on a schedule
with a no-trade band around the target so it is not paying fees to chase noise.
That is the structure the market model rewards, and it is a fair thing to test
— but read the caveat in the report before drawing any conclusion from it:
knowing the shape of the process that generated your data is a luxury nobody
has in a real market.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .config import BARS_PER_DAY, BARS_PER_YEAR, FUNDING_INTERVAL_BARS, SimConfig
from .agent import JournalEntry, RunResult, clock
from .exchange import Account
from .indicators import EMA, Rolling


@dataclass(frozen=True)
class FilterConfig:
    """Settings for the volatility-targeted trend agent."""

    name: str = "vol-targeted trend"
    starting_cash: float = 1_000.0
    signal_half_life_bars: float = BARS_PER_DAY        # the filter's memory
    vol_window: int = 8 * BARS_PER_DAY                 # volatility estimate window
    target_vol: float = 3.00                           # annualised account vol target
    max_leverage: float = 10.0                         # gross notional / equity cap
    signal_cap: float = 2.0                            # clamp on the z-scored forecast
    rebalance_bars: int = 12                           # act once an hour
    no_trade_band: float = 0.25                        # skip trades under this fraction
    max_drawdown_stop: float = 0.75
    daily_loss_limit: float = 0.30
    reserve_cash: float = 0.02
    position_leverage: float = 8.0                     # per-position margin leverage


# A preset that turns the same machinery down to a sane risk level, for the
# side-by-side comparison.
FILTER_BALANCED = FilterConfig(
    name="vol-targeted trend (balanced)",
    target_vol=0.60,
    max_leverage=2.0,
    daily_loss_limit=0.08,
    max_drawdown_stop=0.25,
    reserve_cash=0.30,
    position_leverage=2.0,
)

RUIN_EQUITY = 25.0


class TrendFilterTrader:
    def __init__(self, config: SimConfig, market, filt: FilterConfig) -> None:
        self.cfg = config
        self.f = filt
        self.market = market
        self.account = Account(cash=filt.starting_cash, venue=config.venue)
        alpha = 1.0 - 0.5 ** (1.0 / filt.signal_half_life_bars)
        self.alpha = alpha
        # Stdev of an EMA of iid returns, in units of the return's own stdev.
        self.ema_scale = math.sqrt(alpha / (2.0 - alpha))
        self.sig = {s: EMA(int(2.0 / alpha - 1.0)) for s in market.symbols}
        self.vol = {s: Rolling(filt.vol_window) for s in market.symbols}
        self.prev = {s: None for s in market.symbols}
        self.journal: list[JournalEntry] = []
        self.equity_curve: list[float] = []
        self.cash_curve: list[float] = []
        self.leverage_curve: list[float] = []
        self.daily_equity: list[float] = []
        self.peak_equity = filt.starting_cash
        self.day_start_equity = filt.starting_cash
        self.paused_day: int | None = None
        self.pause_days = 0
        self.halted_at: int | None = None
        self.halt_reason = ""

    def log(self, bar, kind, symbol, equity, text) -> None:
        self.journal.append(JournalEntry(bar, clock(bar), kind, symbol, equity, text))

    def forecast(self, symbol: str) -> float:
        """z-scored trend forecast, clamped, in [-1, 1] after dividing by the cap."""
        ema = self.sig[symbol].value
        sd = self.vol[symbol].std
        if ema is None or sd <= 0:
            return 0.0
        z = ema / (sd * self.ema_scale)
        cap = self.f.signal_cap
        return max(-1.0, min(1.0, z / cap))

    def run(self) -> RunResult:
        m, n, f = self.market, self.market.n_bars, self.f
        self.log(0, "start", "-", self.account.cash,
                 f"Session opened with ${self.account.cash:,.2f}. Strategy: {f.name}; "
                 f"target volatility {f.target_vol:.0%} annualised, "
                 f"gross leverage capped at {f.max_leverage:.0f}x.")

        for i in range(n):
            prices = {s: m.bars[s][i].close for s in m.symbols}
            for s in m.symbols:
                p = prices[s]
                if self.prev[s] is not None and self.prev[s] > 0:
                    r = math.log(p / self.prev[s])
                    self.sig[s].update(r)
                    self.vol[s].update(r)
                self.prev[s] = p

            day = i // BARS_PER_DAY
            if i % BARS_PER_DAY == 0:
                self.day_start_equity = self.account.equity(prices)
                if self.paused_day is not None and day > self.paused_day:
                    self.paused_day = None
                    self.log(i, "resume", "-", self.day_start_equity,
                             "New day, daily loss limit reset. Back on risk.")

            if i > 0 and i % FUNDING_INTERVAL_BARS == 0 and self.account.positions:
                rates = {s: m.funding[s][i] for s in m.symbols}
                paid = self.account.settle_funding(rates, prices)
                if abs(paid) > 0.01:
                    self.log(i, "funding", "-", self.account.equity(prices),
                             f"Funding settled: {'paid' if paid > 0 else 'received'} "
                             f"${abs(paid):,.2f}.")

            self._liquidation_sweep(i, prices)
            equity = self.account.equity(prices)
            self.peak_equity = max(self.peak_equity, equity)
            if self.halted_at is None:
                self._check_kill_switches(i, day, equity, prices)

            if (
                self.halted_at is None
                and self.paused_day is None
                and i % f.rebalance_bars == 0
                and self.vol[m.symbols[0]].ready
            ):
                self._rebalance(i, prices)

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
                         f"({equity / f.starting_cash - 1:+.1%} on the month), "
                         f"gross leverage {self.leverage_curve[-1]:.1f}x.")

        last = {s: m.bars[s][n - 1].close for s in m.symbols}
        for sym in list(self.account.positions):
            self.account.close_position(sym, last[sym], n - 1, "end-of-simulation",
                                        m.spec[sym].adv_usd)
        final = self.account.equity(last)
        self.equity_curve[-1] = final
        self.log(n - 1, "end", "-", final,
                 f"Simulation complete. Final equity ${final:,.2f} "
                 f"({final / f.starting_cash - 1:+.1%}).")

        return RunResult(
            config=self.cfg, equity_curve=self.equity_curve, cash_curve=self.cash_curve,
            leverage_curve=self.leverage_curve, daily_equity=self.daily_equity,
            trades=self.account.trades, journal=self.journal, account=self.account,
            market=self.market, halted_at=self.halted_at, halt_reason=self.halt_reason,
            pause_days=self.pause_days,
        )

    # ---- mechanics -------------------------------------------------------

    def _liquidation_sweep(self, i: int, prices) -> None:
        mm = self.cfg.venue.maintenance_margin
        for sym in list(self.account.positions):
            pos = self.account.positions[sym]
            bar = self.market.bars[sym][i]
            liq = pos.liquidation_price(mm)
            hit = (pos.side > 0 and bar.low <= liq) or (pos.side < 0 and bar.high >= liq)
            if hit:
                t = self.account.liquidate(sym, liq, i)
                self.log(i, "liquidation", sym, self.account.equity(prices),
                         f"LIQUIDATED {sym} at {liq:,.4f}: lost ${-t.net_pnl:,.2f}.")

    def _check_kill_switches(self, i, day, equity, prices) -> None:
        f = self.f

        def flatten(reason: str) -> None:
            for sym in list(self.account.positions):
                self.account.close_position(sym, prices[sym], i, reason,
                                            self.market.spec[sym].adv_usd)

        if equity <= RUIN_EQUITY:
            flatten("ruin")
            self.halted_at, self.halt_reason = i, "account effectively wiped out"
            self.log(i, "halt", "-", equity, f"HALT: equity ${equity:,.2f}. Nothing left.")
            return
        if equity <= self.peak_equity * (1.0 - f.max_drawdown_stop):
            flatten("max-drawdown")
            self.halted_at = i
            self.halt_reason = f"drawdown from peak exceeded {f.max_drawdown_stop:.0%}"
            self.log(i, "halt", "-", equity,
                     f"HALT: {1 - equity / self.peak_equity:.1%} below the "
                     f"${self.peak_equity:,.2f} peak. Circuit breaker tripped.")
            return
        if (self.paused_day is None
                and equity <= self.day_start_equity * (1.0 - f.daily_loss_limit)):
            flatten("daily-loss-limit")
            self.paused_day, self.pause_days = day, self.pause_days + 1
            self.log(i, "pause", "-", equity,
                     f"Daily loss limit: down {1 - equity / self.day_start_equity:.1%} "
                     f"on day {day + 1}. Flat until tomorrow.")

    def _rebalance(self, i: int, prices) -> None:
        f = self.f
        acct = self.account
        equity = acct.equity(prices)
        if equity <= RUIN_EQUITY:
            return

        # Size each leg inversely to its own volatility so no single market
        # dominates the account's risk, then scale the book to the target.
        raw: dict[str, float] = {}
        for sym in self.market.symbols:
            fc = self.forecast(sym)
            sd = self.vol[sym].std
            if abs(fc) < 1e-6 or sd <= 0:
                raw[sym] = 0.0
                continue
            ann_vol = sd * math.sqrt(BARS_PER_YEAR)
            raw[sym] = fc * (f.target_vol / ann_vol) / len(self.market.symbols)

        gross = sum(abs(x) for x in raw.values())
        if gross > f.max_leverage:
            raw = {k: v * f.max_leverage / gross for k, v in raw.items()}

        for sym, weight in raw.items():
            target_notional = weight * equity
            adv = self.market.spec[sym].adv_usd
            price = prices[sym]
            pos = acct.positions.get(sym)
            current = pos.side * pos.qty * price if pos else 0.0
            delta = target_notional - current
            if abs(delta) < max(self.cfg.venue.min_notional,
                                f.no_trade_band * abs(target_notional) + 1e-9):
                continue

            if pos and (target_notional == 0.0 or target_notional * pos.side < 0):
                acct.close_position(sym, price, i, "flip-or-flat", adv)
                pos = None
                current = 0.0
                delta = target_notional

            if abs(target_notional) < self.cfg.venue.min_notional:
                continue

            side = 1 if target_notional > 0 else -1
            if pos is None:
                qty = abs(target_notional) / price
                spendable = max(0.0, acct.cash - equity * f.reserve_cash)
                qty = min(qty, spendable * f.position_leverage / price * 0.98)
                opened = acct.open_position(
                    sym, side, qty, price, i, 0.0 if side > 0 else math.inf, 0.0,
                    f.position_leverage, adv, note=f"filter/{self.forecast(sym):+.2f}",
                )
                if opened:
                    self.log(i, "entry", sym, acct.equity(prices),
                             f"{'LONG' if side > 0 else 'SHORT'} {sym}: forecast "
                             f"{self.forecast(sym):+.2f}, target "
                             f"${abs(target_notional):,.0f} notional "
                             f"({abs(weight):.1f}x equity) at {price:,.4f}.")
            elif abs(target_notional) > abs(current):
                add_qty = (abs(target_notional) - abs(current)) / price
                spendable = max(0.0, acct.cash - equity * f.reserve_cash)
                add_qty = min(add_qty, spendable * f.position_leverage / price * 0.98)
                if acct.add_to_position(sym, add_qty, price, adv):
                    self.log(i, "pyramid", sym, acct.equity(prices),
                             f"Scaled {sym} up to ${abs(target_notional):,.0f} notional — "
                             f"forecast strengthened to {self.forecast(sym):+.2f}.")
            else:
                cut = (abs(current) - abs(target_notional)) / price
                if acct.reduce_position(sym, cut, price, i, adv):
                    self.log(i, "exit", sym, acct.equity(prices),
                             f"Trimmed {sym} to ${abs(target_notional):,.0f} notional — "
                             f"forecast eased to {self.forecast(sym):+.2f}.")


def run_filter_simulation(
    config: SimConfig, filt: FilterConfig | None = None, market=None
) -> RunResult:
    from .market import generate_market

    if market is None:
        market = generate_market(config.universe, config.bars, config.seed,
                                 config.predictability, config.venue)
    return TrendFilterTrader(config, market, filt or FilterConfig()).run()
