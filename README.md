# claude-code-tutorial

Beginner to Advanced interactive Claude Code Tutorial, published as a
[MkDocs Material](https://squidfunk.github.io/mkdocs-material/) site.

- Tutorial content: `docs/`
- Site configuration: `mkdocs.yml`

## stockcast — worked example app

`stockcast/` is a complete example application built alongside the tutorial.
Give it a ticker and a timeframe and it produces a forecast *distribution*
for that stock, informed by current events researched through the `claude`
CLI — so a Claude Pro/Max subscription works and no separate API key is
needed.

```bash
python -m stockcast ORCL 1 week from today   # command line
python -m stockcast --serve                  # local web UI
python -m unittest discover -s tests -t .    # tests
```

No third-party packages are required. It is deliberately uncertainty-first:
the interval is the forecast and the single number is only its midpoint, a
researched view can never move the median further than the data's own
volatility, and research that cannot be *verified* to have actually searched
the web is discarded rather than reported. It is not investment advice.

Full write-up, including the design decisions and their rationale:
[`docs/stock-predictor.md`](docs/stock-predictor.md).
