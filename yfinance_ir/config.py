"""Process-wide configuration for :mod:`yfinance_ir`."""

import os
from dataclasses import dataclass
from typing import Optional

__all__ = ["Config", "get_config", "set_config", "default_cache_dir"]


def default_cache_dir() -> str:
    env = os.environ.get("YFINANCE_IR_CACHE_DIR")
    if env:
        return env
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(base, "yfinance_ir")


@dataclass
class Config:
    #: minimum seconds between two requests to the same host
    min_interval: float = 0.1
    #: per-request timeout in seconds
    timeout: float = 20.0
    #: where ``symbols.sqlite`` lives; ``None`` -> :func:`default_cache_dir`
    cache_dir: Optional[str] = None
    #: worker threads used by :func:`yfinance_ir.download`
    threads: int = 4
    #: ccxt-ir exchange id used for ``*-IRT`` / ``*-USDT`` tickers
    crypto_exchange: str = "nobitex"
    #: honour ``HTTP_PROXY``/``HTTPS_PROXY`` env vars. TSETMC blocks most foreign
    #: exits, so a proxy pointing outside Iran silently turns into a timeout.
    trust_env: bool = True

    def resolved_cache_dir(self) -> str:
        return self.cache_dir or default_cache_dir()


_config = Config()


def get_config() -> Config:
    return _config


def set_config(**kwargs) -> Config:
    """Mutate the global config; unknown keys raise ``TypeError``."""
    for key, value in kwargs.items():
        if not hasattr(_config, key):
            raise TypeError(f"unknown config option: {key!r}")
        setattr(_config, key, value)
    return _config
