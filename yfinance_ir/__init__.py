"""yfinance-style market data for Iranian markets (TSETMC, Codal, TGJU).

Not affiliated with, endorsed by, or connected to yfinance, Yahoo, TSETMC, Codal,
TGJU or the Statistical Centre of Iran. Data comes from those providers' public
endpoints and carries no accuracy guarantee; nothing here is investment advice.
"""

import logging as _logging

from . import _cache as cache  # noqa: F401  (yfinance_ir.cache.clear())
from .config import Config, get_config, set_config
from .exceptions import (
    BlockedError,
    DataUnavailable,
    RateLimitError,
    SymbolNotFound,
    YFIRError,
)
from .multi import download
from .search import Search
from .ticker import Ticker, Tickers

#: a library must not install handlers on the root logger
_logging.getLogger("yfinance_ir").addHandler(_logging.NullHandler())

#: CalVer, YYYY.M.MICRO
__version__ = "2026.9.1"

__all__ = [
    "Ticker",
    "Tickers",
    "download",
    "Search",
    "set_config",
    "get_config",
    "Config",
    "cache",
    "YFIRError",
    "SymbolNotFound",
    "BlockedError",
    "RateLimitError",
    "DataUnavailable",
    "__version__",
]
