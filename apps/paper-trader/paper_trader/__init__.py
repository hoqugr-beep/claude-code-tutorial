"""An autonomous paper-trading simulator.

Everything here is a simulation.  No order is ever sent anywhere, no money is
ever at risk, and no result produced by this package is a prediction about
any real market.
"""

__all__ = ["config", "market", "exchange", "indicators", "strategy", "agent",
           "metrics", "montecarlo", "report"]
