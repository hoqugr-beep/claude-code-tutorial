# stockcast — a worked example

`stockcast` is a small application built in this repository as an end-to-end
example: it takes a request like `ORCL 1 week from today` and produces a
forecast for that stock's price, informed by researched current events.

It is also a case study in a problem that shows up constantly when you build
on a language model: **how do you know the model actually did the work?**

!!! warning "Read this before you use the numbers"
    No tool can reliably predict a specific stock price on a specific future
    date. Over short horizons, stock prices are very close to a random walk.
    `stockcast` is built to be honest about that: its real output is a
    *probability range*, and the headline number is only the midpoint of that
    range. Do not trade on it. It is not investment advice.

## Quick start

No API key and no third-party packages are required. Python 3.10 or newer:

```bash
# Command line
python -m stockcast ORCL 1 week from today

# Skip the research step (offline, no cost)
python -m stockcast ORCL 1 week from today --no-research

# Machine-readable
python -m stockcast NVDA 3 months --json

# Local web UI at http://127.0.0.1:8765
python -m stockcast --serve
```

The web UI also exposes a JSON endpoint: `/api?q=ORCL+1+week`.

## What it does

```
  request  ─┬─►  price history  ─►  volatility  ─►  baseline distribution  ─┐
            │    (keyless feed)      estimate        (zero drift)           │
            │                                                              ├─► forecast
            └─►  current events  ─►  verified?  ─►  bounded adjustment  ────┘
                 (claude + web)       yes/no        (shrink, then cap)
```

### Input

`ORCL 1 week from today`. The parser accepts `1w`, `10 days`, `3 months`,
`tomorrow`, or an explicit `2026-12-31`. Targets landing on a weekend or
market holiday roll forward to the next real session, and the tool says so.

### Price history

Fetched from free, keyless endpoints — Stooq first, then Yahoo Finance, with
the optional `yfinance` package last. These are unofficial and can break
without notice, so providers are tried in order and a total failure reports
what each one said, letting you tell a bad ticker from a network problem.
Results are cached locally for 30 minutes.

### The statistical baseline

Daily log returns give a volatility estimate — both a plain realized standard
deviation and an EWMA (decay 0.94, which weights recent sessions more heavily
so a change in regime shows up quickly). By default the wider of the two is
used, because an interval that is too narrow is the more damaging error.

Volatility is scaled to the horizon by the square root of the number of
trading sessions, giving a lognormal distribution for the price on the target
date.

**The baseline assumes zero drift**, which is the design decision most worth
understanding. It would be easy to measure a stock's recent average daily
return and extrapolate it, but over these horizons that average is
overwhelmingly noise — its standard error is about the same size as any
plausible real drift. Extrapolating it manufactures confident nonsense. So the
baseline says the best guess for the future price is the current price, and
spends its effort on the *width* of the distribution, which can actually be
estimated from data.

### Current events

This is the part you asked for: elections, wars, interest rates, energy,
earnings. `stockcast` shells out to `claude --print`, so it authenticates
exactly the way your Claude Code already does — **a Pro or Max subscription
works, and no separate API key is needed.**

The research pass searches across company news and earnings, central bank
policy, elections and legislation, geopolitics, energy and commodities,
sector competition, and regulatory or litigation exposure. It returns
structured catalysts with source URLs, plus a directional view, a confidence,
and a volatility multiplier for known events inside the window.

## The honesty machinery

Three mechanisms do the real work here, and they are the reason this example
is worth reading.

### 1. Research is verified, not trusted

While building this tool, a research call returned the following:

> Oracle (ORCL) reported record Q1 FY2027 revenue of $19.35 billion, fueled by
> a 121% surge in cloud infrastructure revenue, and raised its full-year
> outlook.
>
> Source: `https://finance.yahoo.com/quote/ORCL/news/`

Confident, specific, sourced — and produced with **zero web searches**. The
model answered from memory and attached a generic landing page. Nothing in the
text distinguishes it from genuine research.

Two traps compounded this. The web-search tool needed to be named explicitly
in the prompt, because a soft "search the web" let the model skip it. And the
obvious verification signal — the `server_tool_use.web_search_requests`
counter in the result JSON — reported `0` **even on runs where search
demonstrably ran**, because the search executed client-side. Trusting that
counter would have rejected the good run while giving no signal on the bad one.

So `stockcast` reads the streamed execution trace and counts actual
`WebSearch` and `WebFetch` tool invocations. If there were none, it raises
rather than returning text, and the forecast falls back to the quantitative
baseline with a loud warning. A forecast is only ever labelled
research-informed when searches provably ran.

!!! tip "The generalisable lesson"
    When you delegate work to a model, verify the *process*, not the shape of
    the output — fabrication and genuine research are textually identical at
    the boundary. Put your verification signal in the execution trace, and
    prove that signal works by testing it against a run you know failed *and*
    a run you know succeeded.

### 2. The narrative's influence is capped by measured uncertainty

A verified research view still cannot run away with the forecast. Two controls
apply in sequence:

* **Shrink** — the model's stated move is multiplied by its own stated
  confidence, so a hedged view barely moves anything.
* **Cap** — the result is then clipped to at most **one standard deviation of
  the baseline's own horizon uncertainty**.

The cap is the load-bearing part, because its size comes from measured data
rather than a hand-picked constant: it tightens automatically wherever the
baseline is confident. Asking a model to "be conservative" is a request, not a
control, and it fails silently exactly when the model is most overconfident.

In testing, a deliberately absurd `+40%` view at maximum confidence was
reduced to the baseline's own 1-sigma, and the output flagged that the cap had
bound. Unverified research is not merely down-weighted — it gets weight zero.

### 3. The output refuses to look more certain than it is

Every forecast reports an 80% and a 95% interval alongside the median, the
probability of finishing higher, the volatility estimate and its lookback, the
raw research view next to the drift actually applied, every source URL, and a
warning list covering stale price data, skipped research, capped views,
rolled-forward dates, and horizons long enough to be meaningless.

## Example output

```
ORCL  →  2026-09-18 (1 week, 5 trading sessions)
==============================================================================

  Last close      537.45   (2026-09-10, via stooq.com)
  Median forecast 539.06   (+0.30%)

  80% interval    485.72  to  594.69   (-9.6% to +10.7%)
  95% interval    460.38  to  627.42

  P(higher than today)  51.1%
  Annualised volatility 56.1%  (max of realized/EWMA over 252 sessions)

Current events  10 web searches, model sonnet
------------------------------------------------------------------------------
  ▲ [high  ] Analysts raised ORCL price targets after the Q1 FY2027 beat...
    https://www.example-source.com/article
  ▼ [high  ] The FOMC decision on 2026-09-16 falls inside the window...
    https://www.example-source.com/fomc

  Scheduled inside the window:
    · FOMC interest rate decision 2026-09-16

  Research view +1.0% at confidence 0.30 → applied drift +0.30%
```

Note how little a plausible, well-sourced, mildly bullish reading moves the
number: **+0.30%**, inside an 80% interval more than twenty points wide. That
is the model behaving correctly. The events are genuinely informative about
*risk*; they are close to uninformative about *direction*.

## Options

| Flag | Effect |
|---|---|
| `--no-research` | Volatility model only. Offline, instant, free. |
| `--json` | Machine-readable output. |
| `--serve` / `--port` / `--host` | Run the local web UI. |
| `--model` | Model for research (default `sonnet`). |
| `--lookback` | Sessions of history for volatility (default 252). |
| `--vol-method` | `realized`, `ewma`, or `max` (default). |
| `--provider` | Force a price source; repeat to set fallback order. |
| `--timeout` | Research timeout in seconds (default 420). |
| `--no-cache` | Bypass the local price cache. |
| `--as-of` | Pretend today is a given date, for testing. |

A research pass costs roughly **$0.30–$0.60** per run against the API, or
counts against your subscription limits. `--no-research` costs nothing.

## Running the tests

```bash
python -m unittest discover -s tests -t .
```

The suite covers the trading calendar, request parsing, the statistical model
(including a check that it recovers a known volatility from a simulated random
walk), provider parsing and fallback, the blend's caps, and HTML escaping. The
research tests are built from real traces captured while developing the tool —
including the fabricated run quoted above, kept as a permanent regression
guard.

## Known limits

* **Short-horizon prices are close to unpredictable.** This is a property of
  markets, not a gap in the implementation. The intervals are the honest part.
* Volatility scaled by √time assumes returns are serially uncorrelated. That
  errs toward *understating* risk in trending markets.
* The lognormal model has thinner tails than real markets. Genuine surprises
  land outside the 95% interval more often than 5% of the time.
* Research quality depends on what is indexed and searchable right now.
* The price feeds are free and unofficial; expect them to break occasionally.
* The web UI has no authentication and each request can spend money. Keep it
  on localhost.
