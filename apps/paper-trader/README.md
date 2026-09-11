# Autonomous Paper Trading Simulator

An agent trades a simulated $1,000 account, flat out, 24/7, for 30 days —
288 decision cycles a day on four synthetic crypto perpetual-futures markets.

**Everything here is a simulation.** Prices are generated, not observed. No
order is placed anywhere, no network call is made, and no money — real or
otherwise — is ever at risk. Nothing produced by this package is a
prediction, a backtest of real history, or investment advice.

Zero dependencies: Python 3.10+ and the standard library.

```bash
cd apps/paper-trader
python3 run_simulation.py                 # headline month + Monte Carlo + report
python3 run_simulation.py --quick         # faster, fewer paths
python3 -m unittest discover -s tests     # the test suite
```

`run_simulation.py` writes `report.html` — a self-contained page with the
equity curve, the outcome distribution, the cost breakdown, and the agent's
own decision journal.

---

## The short version of the result

The brief was "ultra aggressive, make as much money as possible." The
simulator takes that seriously and then reports what actually happens, which
is the useful part:

* **Ultra-aggressive discrete trading loses reliably.** Risking 8% of equity
  per trade at 10x leverage, the agent trips its 75% drawdown circuit breaker
  on the large majority of simulated months. Trading costs, not bad luck, do
  most of the damage — the agent pays a large multiple of its own starting
  capital in fees over a month of constant turnover.
* **A volatility-targeted trend filter does much better than discrete
  entries and stops**, because it stops discretising a weak continuous
  forecast into on/off decisions and stops converting shallow adverse moves
  into realised losses.
* **The outcome depends almost entirely on one unverifiable assumption** —
  how much exploitable structure the market has. The simulator makes that a
  dial (`--predictability`) rather than hiding it, and the report sweeps it.
  At the efficient-market setting, *every* configuration loses to costs, and
  that is not a bug.
* **Aggression is not a strategy.** With an identical signal on identical
  markets, the ultra-aggressive preset and the balanced preset differ by an
  enormous margin in median outcome — in the balanced preset's favour.

Run it yourself and read the distribution, not the single path.

---

## Layout

```
run_simulation.py         CLI: headline run, Monte Carlo, sensitivity, report
tune.py                   parameter search with a train/holdout split
paper_trader/
  config.py               all assumptions, in one place, with their caveats
  market.py               synthetic 24/7 market generator
  exchange.py             margin, fees, funding, liquidation
  indicators.py           incremental EMA / ATR / RSI / Donchian / z-score
  strategy.py             the discrete signal ensemble
  agent.py                the autonomous decision loop
  trend_filter.py         the volatility-targeted continuous-position agent
  metrics.py              performance statistics
  montecarlo.py           many independent paths, in parallel
  report.py               self-contained HTML report
tests/                    generator, exchange and strategy tests
```

---

## How the market is modelled

Four perpetual-futures markets on 5-minute bars, generated as a
regime-switching jump diffusion with a shared market factor.

Three choices are worth calling out, because each one is a place where a
simulator can quietly hand the strategy free money:

**Regimes change volatility only, never drift.** Volatility clustering is a
well-established property of financial returns. Regime-dependent drift is
not, and baking it in creates exploitable structure — which would mean the
`predictability = 0` setting is not actually a null hypothesis. It has to be
one, or the entire sensitivity analysis is meaningless.

**Intrabar highs and lows are sampled from the exact Brownian-bridge
distribution**, not invented with an ad-hoc wick model. For a bridge from 0
to `b` over one bar with volatility σ, `P(max ≥ m) = exp(-2m(m-b)/σ²)`, which
inverts to `m = (b + sqrt(b² - 2σ² ln u)) / 2` for a uniform draw `u`. Get
this wrong and the generated range is inconsistent with the generated
close-to-close volatility — which hands every stop-based strategy a stream of
free losses that exist only in the generator. `tests/test_market.py` measures
the range back out of the generated data and checks it against theory.

**Funding is small and clipped.** Real perpetual funding is a handful of
basis points per 8 hours, spiking to a few tenths of a percent. An early
version of this model charged roughly ten times that and systematically
punished exactly the positions a trend-follower holds. The test suite now
asserts the annualised funding cost of a permanently-long position stays in a
plausible range.

### The predictability dial

`--predictability` is the load-bearing assumption, so it is an explicit
parameter rather than something buried in the generator. It is defined as
**the approximate annualised Sharpe ratio a well-matched trend filter can
extract from the price series before costs**:

| Setting | Meaning |
|---|---|
| `0.0` | Efficient market. No technical strategy can have positive expectancy once costs are paid. The null hypothesis. |
| `0.5` | The default. Roughly what a good systematic trend programme might target gross. Optimistic, not absurd. |
| `1.0`+ | A market with structure a retail agent almost certainly cannot access. |

Note the definition is deliberately *not* "the Sharpe a perfect forecaster
would earn". A perfect forecaster knows the latent state exactly; a filter
reading prices recovers it only with correlation `≈ k·sqrt(H·dt)`, a few
percent for a one-day half-life on 5-minute bars. Scaling the dial to perfect
foresight produces a market that looks predictable on paper and is
untradeable in practice — which is a good way to build a simulator that
flatters every strategy you test on it.

The scaling constant is calibrated empirically, not derived and trusted:
`tests/test_market.py::TestPredictabilityCalibration` runs a matched filter
over generated data and checks the Sharpe it actually achieves against the
dial.

**No claim is made about which value matches any real market.** That is the
point of making it a dial.

---

## How the venue is modelled

Isolated margin, taker fills only.

* Taker fee on notional, plus a half-spread, plus square-root market impact
  scaled by each market's average daily volume.
* Funding settles every 8 hours against position margin, which is what moves
  the liquidation price on a real isolated-margin venue.
* Liquidation is checked against intrabar highs and lows, not just closes —
  wicks are how leveraged accounts actually die.
* Within a bar, the adverse extreme is assumed to be touched before the
  favourable one, and a gap through a trigger fills at the open. Both
  conventions are deliberately pessimistic.
* Losses are capped at posted margin; a gap beyond that is absorbed by the
  venue, as an insurance fund would.

The central invariant, enforced by `tests/test_exchange.py`: **realised P&L
equals the change in account equity**, always. P&L is defined as cash
returned minus cash invested — a difference between quantities the ledger
already tracks — rather than reconstructed from gross-minus-fees, so the two
can never drift apart.

**Every venue parameter is an order-of-magnitude estimate, not a measurement
from a primary source.** They are plausible. They are not verified. If the
numbers matter to you, replace them in `config.py` with values you have
measured yourself.

---

## The two agents

### `agent.py` — discrete, ultra-aggressive

An ensemble of trend, breakout, momentum, mean-reversion and funding-tilt
signals produces one score in `[-1, +1]`; sign is direction, magnitude scales
size. Positions are sized to risk a fixed fraction of equity to an
ATR-based stop, with per-position leverage chosen so the stop always sits
inside the liquidation price — otherwise the risk model is fiction, because
the position dies before its stop can fire.

Risk management runs before new entries every cycle: liquidation, stops,
trailing stops, targets, time stops, pyramiding, a daily loss limit, and a
hard drawdown circuit breaker.

### `trend_filter.py` — continuous, volatility-targeted

Holds a position proportional to a z-scored trend forecast, sized so each
market contributes comparable risk and the book runs at a target volatility,
rebalanced on a schedule with a no-trade band so it is not paying fees to
chase noise.

This does substantially better, and there is a caveat you should not skip:
its structure matches the process that generates the data. Knowing the shape
of your market's data-generating process is a luxury nobody has in a real
market, so treat its results as an upper bound on this model, not as an
achievable target anywhere else.

---

## Using real data instead

`market.load_csv_market` takes one CSV per symbol with a header row and the
columns `open,high,low,close,volume_usd`. All files must have the same number
of rows, aligned in time — the loader does not resample or join on
timestamps, so do that wherever you exported the data.

There is deliberately no built-in exchange downloader: pinning this package
to a specific venue's API shape would add a dependency, a rate limit, and a
thing to break, for data you can export in one step from wherever you already
trust.

---

## Tuning honestly

`tune.py` searches risk configurations under two rules that make it a search
rather than a way to fool yourself:

1. **Train/holdout split.** Configurations are ranked on one set of market
   seeds and re-scored on a disjoint set they were never selected on. The
   gap between the two — the script prints it as *selection shrinkage* — is
   how much of the training result was luck.
2. **Median, not mean.** With leverage the mean is dragged around by a
   handful of lucky paths. The median is what a typical month looks like.

```bash
python3 tune.py --trials 72 --train 16 --holdout 32
```

---

## What this simulator does not model

Any of these could change the conclusions, and all of them exist in real
trading:

* Exchange outages, rate limits, rejected orders, and API failures — which
  cluster in exactly the conditions where an aggressive agent most wants to
  trade.
* Fills materially worse than modelled during a real liquidation cascade.
* Counterparty and custody risk. The venue is assumed solvent and honest.
* Tax, borrow limits, and position limits.
* Bugs in the agent's own code, which in live trading is a leading cause of
  loss.
* Any market microstructure below the 5-minute bar.

---

*Simulation only. Not investment advice. No order was ever placed anywhere.*
