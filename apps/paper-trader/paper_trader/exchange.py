"""A simulated perpetual-futures venue: margin, fees, funding, liquidation.

Accounting model
----------------
* Isolated margin per position.  `account.cash` is free collateral; each open
  position holds `position.margin` that is returned (plus or minus P&L) on
  close.
* ``equity = cash + sum(margin + unrealised_pnl)``.
* Taker fills only.  Every fill pays the half-spread plus a square-root
  impact term, plus the taker fee on notional.
* Funding settles every 8 hours and is debited from (or credited to) the
  position's margin, which is what moves the liquidation price on a real
  isolated-margin venue.
* Liquidation is checked against the bar's high/low, not just the close, so
  intrabar wicks can take a position out — which is how leveraged accounts
  actually die.

Intrabar convention: within one bar we assume the adverse extreme is touched
before the favourable one.  That is the conservative assumption and it makes
the reported results a lower bound on this model's path, not an upper one.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .config import VenueConfig


@dataclass
class Position:
    symbol: str
    side: int                    # +1 long, -1 short
    qty: float
    entry_price: float
    margin: float
    leverage: float
    opened_bar: int
    stop: float
    take_profit: float
    risk_per_unit: float         # |entry - initial stop|, the "1R" distance
    extreme_price: float         # best price seen, drives the trailing stop
    pyramids: int = 0
    fees_paid: float = 0.0
    funding_paid: float = 0.0
    invested_cash: float = 0.0   # every dollar of cash paid into this position
    note: str = ""

    @property
    def notional_at_entry(self) -> float:
        return self.qty * self.entry_price

    def notional(self, price: float) -> float:
        return self.qty * price

    def unrealised(self, price: float) -> float:
        return self.side * self.qty * (price - self.entry_price)

    def equity(self, price: float) -> float:
        return self.margin + self.unrealised(price)

    def liquidation_price(self, maintenance_margin: float) -> float:
        """Price at which position equity falls to the maintenance requirement."""
        if self.qty <= 0:
            return 0.0 if self.side > 0 else math.inf
        per_unit_margin = self.margin / self.qty
        if self.side > 0:
            return max(0.0, (self.entry_price - per_unit_margin) / (1.0 - maintenance_margin))
        return (self.entry_price + per_unit_margin) / (1.0 + maintenance_margin)


@dataclass
class Trade:
    symbol: str
    side: int
    qty: float
    entry_bar: int
    exit_bar: int
    entry_price: float
    exit_price: float
    gross_pnl: float
    fees: float
    funding: float
    net_pnl: float
    r_multiple: float
    reason: str
    note: str = ""


@dataclass
class Account:
    cash: float
    venue: VenueConfig
    positions: dict[str, Position] = field(default_factory=dict)
    trades: list[Trade] = field(default_factory=list)
    fees_total: float = 0.0
    funding_total: float = 0.0
    liquidations: int = 0
    rejected_orders: int = 0

    # ---- valuation -------------------------------------------------------

    def equity(self, prices: dict[str, float]) -> float:
        total = self.cash
        for sym, pos in self.positions.items():
            total += pos.equity(prices[sym])
        return total

    def gross_notional(self, prices: dict[str, float]) -> float:
        return sum(pos.notional(prices[sym]) for sym, pos in self.positions.items())

    def leverage(self, prices: dict[str, float]) -> float:
        eq = self.equity(prices)
        return self.gross_notional(prices) / eq if eq > 0 else math.inf

    # ---- execution -------------------------------------------------------

    def fill_price(self, mark: float, side: int, notional: float, adv_usd: float) -> float:
        """Taker fill price including half-spread and square-root impact."""
        v = self.venue
        impact = 0.0
        if adv_usd > 0 and notional > 0:
            impact = v.impact_coef * math.sqrt(notional / adv_usd)
        cost = v.base_spread + impact
        return mark * (1.0 + side * cost)

    def open_position(
        self,
        symbol: str,
        side: int,
        qty: float,
        mark: float,
        bar: int,
        stop: float,
        take_profit: float,
        leverage: float,
        adv_usd: float,
        note: str = "",
    ) -> Position | None:
        """Open a new position.  Returns None if the venue or margin rejects it."""
        v = self.venue
        if symbol in self.positions:
            raise ValueError(f"position already open on {symbol}")
        if qty <= 0:
            self.rejected_orders += 1
            return None

        price = self.fill_price(mark, side, qty * mark, adv_usd)
        notional = qty * price
        if notional < v.min_notional:
            self.rejected_orders += 1
            return None

        leverage = min(leverage, v.max_leverage)
        margin = notional / leverage
        fee = notional * v.taker_fee
        if margin + fee > self.cash:
            self.rejected_orders += 1
            return None

        self.cash -= margin + fee
        self.fees_total += fee
        pos = Position(
            symbol=symbol,
            side=side,
            qty=qty,
            entry_price=price,
            margin=margin,
            leverage=leverage,
            opened_bar=bar,
            stop=stop,
            take_profit=take_profit,
            risk_per_unit=abs(price - stop),
            extreme_price=price,
            fees_paid=fee,
            invested_cash=margin + fee,
            note=note,
        )
        self.positions[symbol] = pos
        return pos

    def add_to_position(
        self, symbol: str, qty: float, mark: float, adv_usd: float
    ) -> bool:
        """Pyramid into an existing position at the same leverage."""
        v = self.venue
        pos = self.positions[symbol]
        if qty <= 0:
            return False
        price = self.fill_price(mark, pos.side, qty * mark, adv_usd)
        notional = qty * price
        if notional < v.min_notional:
            return False
        margin = notional / pos.leverage
        fee = notional * v.taker_fee
        if margin + fee > self.cash:
            self.rejected_orders += 1
            return False

        self.cash -= margin + fee
        self.fees_total += fee
        total_qty = pos.qty + qty
        pos.entry_price = (pos.entry_price * pos.qty + price * qty) / total_qty
        pos.qty = total_qty
        pos.margin += margin
        pos.fees_paid += fee
        pos.invested_cash += margin + fee
        pos.pyramids += 1
        return True

    def reduce_position(
        self, symbol: str, qty: float, mark: float, bar: int, adv_usd: float
    ) -> float:
        """Partially close a position, returning the realised cash P&L.

        Margin is released pro rata, so the remaining position keeps the same
        leverage and the same liquidation price.
        """
        v = self.venue
        pos = self.positions[symbol]
        qty = min(qty, pos.qty)
        if qty <= 0 or qty * mark < v.min_notional:
            return 0.0
        if qty >= pos.qty * 0.999:
            return self.close_position(symbol, mark, bar, "resize", adv_usd).net_pnl

        price = self.fill_price(mark, -pos.side, qty * mark, adv_usd)
        share = qty / pos.qty
        released = pos.margin * share
        invested = pos.invested_cash * share
        entry_fees = pos.fees_paid * share
        funding = pos.funding_paid * share
        gross = pos.side * qty * (price - pos.entry_price)
        fee = qty * price * v.taker_fee
        proceeds = max(0.0, released + gross - fee)

        self.cash += proceeds
        self.fees_total += fee
        pos.qty -= qty
        pos.margin -= released
        pos.invested_cash -= invested
        pos.fees_paid -= entry_fees
        pos.funding_paid -= funding

        # A partial close is a completed round trip for that quantity, so it
        # gets its own trade record.  Without one the realised P&L exists in
        # the cash balance but not in the trade log, and the two stop agreeing.
        risk_total = pos.risk_per_unit * qty
        net = proceeds - invested
        self.trades.append(
            Trade(
                symbol=symbol,
                side=pos.side,
                qty=qty,
                entry_bar=pos.opened_bar,
                exit_bar=bar,
                entry_price=pos.entry_price,
                exit_price=price,
                gross_pnl=gross,
                fees=entry_fees + fee,
                funding=funding,
                net_pnl=net,
                r_multiple=(net / risk_total) if risk_total > 0 else 0.0,
                reason="trim",
                note=pos.note,
            )
        )
        return net

    def close_position(
        self,
        symbol: str,
        mark: float,
        bar: int,
        reason: str,
        adv_usd: float,
        override_price: float | None = None,
    ) -> Trade:
        """Close a position in full at `mark` (or exactly at `override_price`)."""
        v = self.venue
        pos = self.positions.pop(symbol)
        exit_side = -pos.side
        if override_price is not None:
            price = override_price
        else:
            price = self.fill_price(mark, exit_side, pos.qty * mark, adv_usd)

        gross = pos.side * pos.qty * (price - pos.entry_price)
        fee = pos.qty * price * v.taker_fee
        self.fees_total += fee
        # Isolated margin: the account cannot lose more than the margin it
        # posted.  A gap through the liquidation price is absorbed by the
        # venue's insurance fund, exactly as it is on a real exchange.
        proceeds = max(0.0, pos.margin + gross - fee)
        self.cash += proceeds

        risk_total = pos.risk_per_unit * pos.qty
        # Realised P&L defined as cash out minus cash in, so it always ties
        # back to the change in account equity.
        net = proceeds - pos.invested_cash
        trade = Trade(
            symbol=symbol,
            side=pos.side,
            qty=pos.qty,
            entry_bar=pos.opened_bar,
            exit_bar=bar,
            entry_price=pos.entry_price,
            exit_price=price,
            gross_pnl=gross,
            fees=pos.fees_paid + fee,
            funding=pos.funding_paid,
            net_pnl=net,
            r_multiple=(net / risk_total) if risk_total > 0 else 0.0,
            reason=reason,
            note=pos.note,
        )
        self.trades.append(trade)
        return trade

    def liquidate(self, symbol: str, liq_price: float, bar: int) -> Trade:
        """Force-close at the liquidation price with the venue penalty."""
        v = self.venue
        pos = self.positions.pop(symbol)
        gross = pos.side * pos.qty * (liq_price - pos.entry_price)
        penalty = pos.qty * liq_price * v.liquidation_penalty
        recovered = max(0.0, pos.margin + gross - penalty)
        self.cash += recovered
        self.fees_total += penalty
        self.liquidations += 1

        risk_total = pos.risk_per_unit * pos.qty
        net = recovered - pos.invested_cash
        trade = Trade(
            symbol=symbol,
            side=pos.side,
            qty=pos.qty,
            entry_bar=pos.opened_bar,
            exit_bar=bar,
            entry_price=pos.entry_price,
            exit_price=liq_price,
            gross_pnl=gross,
            fees=pos.fees_paid + penalty,
            funding=pos.funding_paid,
            net_pnl=net,
            r_multiple=(net / risk_total) if risk_total > 0 else 0.0,
            reason="liquidated",
            note=pos.note,
        )
        self.trades.append(trade)
        return trade

    # ---- periodic mechanics ---------------------------------------------

    def settle_funding(self, rates: dict[str, float], prices: dict[str, float]) -> float:
        """Debit/credit 8-hourly funding against each position's margin."""
        total = 0.0
        for sym, pos in self.positions.items():
            payment = pos.notional(prices[sym]) * rates[sym] * pos.side
            pos.margin -= payment
            pos.funding_paid += payment
            total += payment
        self.funding_total += total
        return total
