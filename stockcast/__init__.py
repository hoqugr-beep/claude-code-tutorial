"""stockcast — a transparent, uncertainty-first stock forecasting tool.

This package produces a *probability distribution* for a ticker's price at a
future date, not a confident point prediction. The headline number is the
median of that distribution; the interval around it is the real output.

See ``docs/stock-predictor.md`` for the model's assumptions and limits.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
