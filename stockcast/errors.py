"""Exception types shared across stockcast."""


class StockcastError(Exception):
    """Base class for every error this package raises deliberately."""


class ParseError(StockcastError):
    """The user's request could not be understood."""


class MarketDataError(StockcastError):
    """Price history could not be retrieved or was unusable."""


class ResearchError(StockcastError):
    """The current-events research step could not be completed.

    Raised in particular when research ran but could not be *verified* as
    having actually searched the web. Callers should degrade to a
    quantitative-only forecast and say so, never silently substitute
    unsourced model recall for research.
    """
