"""``download([...])`` -- multi-symbol history with the yfinance MultiIndex layout."""

import logging
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, Sequence, Union

import pandas as pd
import requests

from ._http import new_session
from .config import get_config
from .exceptions import YFIRError
from .ticker import Ticker, _split_symbols

__all__ = ["download"]

_log = logging.getLogger("yfinance_ir")


def download(
    tickers: Union[str, Sequence[str]],
    start=None,
    end=None,
    period: str = "max",
    interval: str = "1d",
    group_by: str = "column",
    auto_adjust: bool = True,
    actions: bool = False,
    threads: Union[bool, int] = True,
    progress: bool = True,
    jalali: bool = False,
    session: Optional[requests.Session] = None,
) -> pd.DataFrame:
    """Per-symbol :meth:`Ticker.history`, concatenated column-wise.

    Failures are logged at WARNING and the symbol is dropped, as yfinance does; an
    all-failed download returns an empty DataFrame rather than raising. The
    ``progress`` bar is written only when ``sys.stdout`` is a terminal, so redirected
    output stays free of carriage returns.
    """
    symbols = _split_symbols(tickers)
    if not symbols:
        return pd.DataFrame()
    session = session or new_session()
    config = get_config()
    workers = (config.threads if threads is True else int(threads or 1))
    workers = max(1, min(workers, len(symbols)))

    kwargs = dict(
        period=period,
        start=start,
        end=end,
        interval=interval,
        auto_adjust=auto_adjust,
        actions=actions,
        jalali=jalali,
    )

    done = {"n": 0}
    done_lock = threading.Lock()
    show_progress = progress and sys.stdout.isatty()

    def _one(symbol: str):
        try:
            return symbol, Ticker(symbol, session=session).history(**kwargs)
        except (YFIRError, ValueError, NotImplementedError) as exc:
            _log.warning("download: %s failed (%s: %s)", symbol, type(exc).__name__, exc)
            return symbol, None
        finally:
            with done_lock:
                done["n"] += 1
                seen = done["n"]
            if show_progress:
                _progress(seen, len(symbols))

    if workers > 1:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_one, symbols))
    else:
        results = [_one(symbol) for symbol in symbols]
    if show_progress:
        sys.stdout.write("\n")
        sys.stdout.flush()

    frames = [(symbol, frame) for symbol, frame in results if frame is not None and not frame.empty]
    if not frames:
        return pd.DataFrame()
    if len(symbols) == 1:
        return frames[0][1]

    merged = pd.concat(
        [frame for _, frame in frames],
        axis=1,
        keys=[symbol for symbol, _ in frames],
    )
    merged.columns.names = ["Ticker", "Price"]
    if group_by == "column":
        merged = merged.swaplevel(axis=1)
        merged.columns.names = ["Price", "Ticker"]
        merged = merged.sort_index(axis=1, level=0, sort_remaining=False)
    return merged


def _progress(done: int, total: int) -> None:
    filled = int(20 * done / total)
    bar = "*" * filled + " " * (20 - filled)
    sys.stdout.write(f"\r[{bar}{int(100 * done / total):>4}%] {done} of {total} completed")
    sys.stdout.flush()
