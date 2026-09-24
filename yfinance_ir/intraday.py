"""Intraday bars rebuilt from TSETMC's trade feed.

TSETMC publishes no intraday OHLCV. ``Trade/GetTradeHistory/{ins}/{dEven}/false`` lists
every trade of a past session and ``Trade/GetTrade/{ins}`` those of the latest one; a row
carries ``nTran`` (sequence number), ``hEven`` (``HHMMSS`` on the Tehran clock),
``qTitTran`` (shares), ``pTran`` (price) and ``canceled``. With cancelled rows dropped and
each ``nTran`` kept once, the trades reproduce TSETMC's daily bar exactly: trade count,
volume, first, high, low and last price (checked on فولاد for 2023-09-30, 2024-09-30 and
2026-09-19 to 2026-09-22). Cancelled rows are not rare: 614 of the 7,090 on فولاد's
2024-09-30, many listed twice (at trade time and at cancel time). One backend also repeats
live rows verbatim: 78,339 rows for 2026-09-19's 78,299 trades.

A bar starts on its interval boundary of the Tehran wall clock, and only buckets that
traded get a bar. Every trading day costs one request, so one call spans at most
:data:`MAX_DAYS` calendar days.

The feed is served by several backends behind ``cdn.tsetmc.com``, and a keep-alive
connection stays on one. On 2026-09-24 about a third of new connections landed on a backend
that answered HTTP 500, or an empty list for a day that traded; a session pinned to one
failed every request for over six minutes, while a connection to a sound backend answered
24 requests out of 24. A failed request therefore drops the session's connections (see
:func:`_attempt`), and the day is fetched again in a later pass, after the other days. The
pause between passes doubles from :data:`RETRY_DELAY` to :data:`MAX_RETRY_DELAY`, about three
minutes over :data:`ATTEMPTS` passes in case every backend fails at once; long pauses are
logged at WARNING. Then :class:`~yfinance_ir.exceptions.DataUnavailable` is raised, since a
missing day would read as "no trading".
"""

import datetime as _dt
import logging
import time
from typing import Callable, Dict, List, Optional, Tuple, TypeVar

import pandas as pd
import requests

from ._dates import date_to_deven, deven_to_date
from .exceptions import DataUnavailable
from .resolver import Instrument
from .sources import tsetmc

__all__ = [
    "INTERVALS",
    "MAX_DAYS",
    "ATTEMPTS",
    "RETRY_DELAY",
    "MAX_RETRY_DELAY",
    "TIMEZONE",
    "COLUMNS",
    "fetch_trades",
    "bars",
]

#: yfinance interval -> pandas frequency
INTERVALS = {
    "1m": "1min",
    "2m": "2min",
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "60m": "60min",
    "90m": "90min",
    "1h": "60min",
}

#: calendar days one call may span; ``period="3mo"`` is 92 days
MAX_DAYS = 92

#: passes over the days that have not answered yet
ATTEMPTS = 12

#: seconds before the second pass; doubles on each further pass
RETRY_DELAY = 0.5

#: longest pause between two passes, in seconds; 181.5 s of pauses in all
MAX_RETRY_DELAY = 30.0

#: pauses at least this long are logged at WARNING, shorter ones at DEBUG
_LOUD_PAUSE = 8.0

TIMEZONE = "Asia/Tehran"

COLUMNS = ["Open", "High", "Low", "Close", "Volume", "Value", "Count"]

_Session = Tuple[_dt.date, str, bool]
_T = TypeVar("_T")

_log = logging.getLogger("yfinance_ir")


def _empty() -> pd.DataFrame:
    frame = pd.DataFrame(columns=COLUMNS, dtype="float64")
    frame.index = pd.DatetimeIndex([], name="Datetime")
    return frame


def _window(start: Optional[_dt.date], end: Optional[_dt.date]) -> Tuple[_dt.date, _dt.date]:
    """``(first, last)`` session days, both inclusive; ``end`` is exclusive."""
    limit = f"intraday history spans at most 3 months ({MAX_DAYS} days) per call"
    if start is None:
        raise ValueError(f"{limit}; pass period='1d' to '3mo' or a start date")
    # TSETMC dates its sessions on the Tehran calendar, whatever the machine's zone
    last = end - _dt.timedelta(days=1) if end is not None else pd.Timestamp.now(tz=TIMEZONE).date()
    if (last - start).days > MAX_DAYS:
        raise ValueError(f"{limit}; {start} to {last} is {(last - start).days} days")
    return start, last


def _sessions(session: requests.Session, instrument: Instrument) -> List[_Session]:
    """``(day, ins_code, is_latest_session)`` for every day the instrument traded, oldest first."""
    days: Dict[_dt.date, str] = {}
    # the primary code goes last so it wins a day that an older listing also reports
    for code in list(instrument.alt_ins_codes) + [instrument.ins_code]:
        try:
            rows = tsetmc.closing_price_daily_list(session, code)
        except DataUnavailable:
            continue
        for row in rows:
            if (row.get("zTotTran") or 0) > 0:
                days[deven_to_date(row["dEven"])] = code
    # the running session is in GetClosingPriceInfo before it reaches the daily list
    quote = tsetmc.closing_price_info(session, instrument.ins_code)
    latest = deven_to_date(quote["dEven"]) if quote.get("dEven") else None
    if latest is not None and (quote.get("zTotTran") or 0) > 0:
        days[latest] = instrument.ins_code
    return [(day, code, day == latest) for day, code in sorted(days.items())]


def _attempt(session: requests.Session, ins_code: str, day: _dt.date, latest: bool) -> Optional[List[dict]]:
    """One request; ``None`` when TSETMC answered HTTP 500 or no rows.

    A failure also drops the session's pooled connections. ``cdn.tsetmc.com`` spreads TCP
    connections over several backends and a keep-alive connection stays on its backend: one
    with a broken trade feed failed every request for over six minutes, while a connection
    on a sound one answered 24 of 24. A new connection draws a backend again.
    """
    try:
        if latest:
            rows = tsetmc.trades(session, ins_code)
        else:
            rows = tsetmc.trade_history(session, ins_code, date_to_deven(day))
    except DataUnavailable as exc:
        if exc.status != 500:
            raise
        rows = []
    if not rows:
        session.close()  # the adapters stay mounted; the next request opens a new connection
        return None
    return rows


def _fetch(
    session: requests.Session,
    days: List[_Session],
    reduce: Callable[[_dt.date, List[dict]], _T],
) -> Dict[_dt.date, _T]:
    """``reduce(day, trades)`` for every day, in passes over the days still missing.

    Reducing as soon as a day arrives keeps one day's trades in memory at a time.
    """
    done: Dict[_dt.date, _T] = {}
    pending = list(days)
    for attempt in range(ATTEMPTS):
        if attempt:
            pause = min(RETRY_DELAY * 2 ** (attempt - 1), MAX_RETRY_DELAY)
            _log.log(
                logging.WARNING if pause >= _LOUD_PAUSE else logging.DEBUG,
                "TSETMC trade feed: no trades yet for %d day(s) from %s; pass %d of %d in %.1f s",
                len(pending),
                pending[0][0].isoformat(),
                attempt + 1,
                ATTEMPTS,
                pause,
            )
            time.sleep(pause)
        missing = []
        for day, code, latest in pending:
            rows = _attempt(session, code, day, latest)
            if rows is None:
                missing.append((day, code, latest))
            else:
                done[day] = reduce(day, rows)
        pending = missing
        if not pending:
            return done
    failed = ", ".join(day.isoformat() for day, _, _ in pending)
    raise DataUnavailable(
        0,
        "",
        f"TSETMC returned no trades for {pending[0][1]} on {failed} in {ATTEMPTS} attempts; "
        "try again later",
    )


def fetch_trades(
    session: requests.Session, ins_code: str, day: _dt.date, *, latest: bool = False
) -> List[dict]:
    """Every trade of ``day``, retried like :func:`bars` does.

    ``latest`` reads ``Trade/GetTrade``, the feed of the latest (possibly running) session.
    """
    return _fetch(session, [(day, ins_code, latest)], lambda _day, rows: rows)[day]


def _day_bars(day: _dt.date, rows: List[dict], freq: str) -> pd.DataFrame:
    trades = pd.DataFrame(rows, columns=["nTran", "hEven", "qTitTran", "pTran", "canceled"])
    trades = trades[trades["canceled"].fillna(0) == 0].drop_duplicates("nTran")
    trades = trades.sort_values(["hEven", "nTran"], kind="stable")
    if trades.empty:
        return _empty()
    clock = trades["hEven"].astype("int64").to_numpy()
    seconds = clock // 10000 * 3600 + clock // 100 % 100 * 60 + clock % 100
    price = trades["pTran"].astype("float64").to_numpy()
    volume = trades["qTitTran"].astype("float64").to_numpy()
    ticks = pd.DataFrame(
        {"price": price, "volume": volume, "value": price * volume},
        index=pd.Timestamp(day) + pd.to_timedelta(seconds, unit="s"),
    )
    grouped = ticks.groupby(ticks.index.floor(freq))
    return pd.DataFrame(
        {
            "Open": grouped["price"].first(),
            "High": grouped["price"].max(),
            "Low": grouped["price"].min(),
            "Close": grouped["price"].last(),
            "Volume": grouped["volume"].sum(),
            "Value": grouped["value"].sum(),
            "Count": grouped["price"].count().astype("float64"),
        }
    )


def bars(
    session: requests.Session,
    instrument: Instrument,
    *,
    start: Optional[_dt.date],
    end: Optional[_dt.date],
    interval: str,
) -> Tuple[pd.DataFrame, pd.DatetimeIndex]:
    """``(bars, sessions)``.

    ``bars`` are raw OHLCV, ascending, indexed by the naive Tehran wall clock. ``sessions``
    is every day the instrument traded, window or not, so that a corporate action can be put
    on the first session at or after its ex-date.
    """
    freq = INTERVALS[interval]
    first, last = _window(start, end)
    sessions = _sessions(session, instrument)
    days = [entry for entry in sessions if first <= entry[0] <= last]
    fetched = _fetch(session, days, lambda day, rows: _day_bars(day, rows, freq))
    frames = [fetched[day] for day, _, _ in days if not fetched[day].empty]
    frame = pd.concat(frames) if frames else _empty()
    frame.index = pd.DatetimeIndex(frame.index, name="Datetime")
    return frame, pd.DatetimeIndex([pd.Timestamp(day) for day, _, _ in sessions], name="Date")
