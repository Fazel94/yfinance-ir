"""Exception hierarchy for :mod:`yfinance_ir`."""

__all__ = [
    "YFIRError",
    "SymbolNotFound",
    "BlockedError",
    "RateLimitError",
    "DataUnavailable",
]


class YFIRError(Exception):
    """Base class for every error raised by this package."""


class SymbolNotFound(YFIRError):
    """The requested symbol could not be resolved to an instrument."""

    def __init__(self, query: str):
        self.query = query
        super().__init__(f"symbol not found: {query!r}")


class BlockedError(YFIRError):
    """The upstream host answered with a WAF / geo-block page instead of data."""


class RateLimitError(YFIRError):
    """The upstream host is rate limiting us (HTTP 429 after retries)."""


class DataUnavailable(YFIRError):
    """The endpoint exists but has no data for this instrument."""

    def __init__(self, status: int, url: str, message: str = ""):
        self.status = status
        self.url = url
        super().__init__(message or f"data unavailable (HTTP {status}): {url}")
