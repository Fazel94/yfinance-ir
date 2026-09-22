"""Daily OHLCV history in the yfinance column layout, plus client-side price adjustment.

Adjustment model (TSETMC publishes no adjusted series):

``ClosingPrice/GetPriceAdjustList`` returns one row per corporate event with the
previous close both **adjusted** (``pClosing``) and **unadjusted**
(``pClosingNotAdjusted``); ``dEven`` is the ex-date. Every bar strictly before an
ex-date is multiplied by ``pClosing / pClosingNotAdjusted``, so the factor applied to a
bar is the product of the ratios of all later events -- a reverse cumulative product.
The per-share cash difference (``unadjusted - adjusted``) is reported as ``Dividends``
on the ex-date, except when a share-count change lands within +/-3 days of the same
event, in which case it is a capital increase and becomes ``Stock Splits``
(``numberOfShareNew / numberOfShareOld``).

TSETMC's adjust list omits most capital increases (for فولاد it holds 23 dividend rows
and one 2019 increase while the share count went 209B -> 1935B in 2020-2026), so every
``Instrument/GetInstrumentShareChange`` row without an adjust row within +/-3 days is
treated as a bonus issue: ``Stock Splits = new / old`` on its date and bars before it
multiplied by ``old / new``. Rights issues paid in cash are therefore over-adjusted.
Funds (``kind == "ETF"``) skip the share-change list entirely: their unit count moves
with every creation and redemption (آوند went 10,000 -> 30,309 Rial in 2022-2026 while
its unit count grew nearly 20x), so only TSETMC's own adjust rows apply to them.
"""

import datetime as _dt
from typing import List, Optional, Tuple

import numpy as np
import pandas as pd
import requests

from ._dates import date_to_deven, deven_to_date, parse_date, period_start, to_jalali
from .exceptions import DataUnavailable
from .resolver import Instrument
from .sources import sci, tgju, tsetmc

#: CPI is published monthly, so `1d` (the default) and `1mo` both return the same frame
_ALLOWED_INTERVALS = {"crypto": {"1d", "1h"}, "sci": {"1d", "1mo"}}

__all__ = ["fetch_daily", "fetch_actions", "history", "BASE_COLUMNS"]

BASE_COLUMNS = ["Open", "High", "Low", "Close", "Volume", "Dividends", "Stock Splits"]

_EMPTY_ACTIONS = (
    pd.Series(dtype="float64", name="Dividends"),
    pd.Series(dtype="float64", name="Stock Splits"),
)


def _empty_frame(extra: Optional[List[str]] = None) -> pd.DataFrame:
    frame = pd.DataFrame(columns=BASE_COLUMNS + list(extra or []))
    frame.index = pd.DatetimeIndex([], name="Date")
    return frame


def _tsetmc_daily(session: requests.Session, ins_codes: List[str]) -> pd.DataFrame:
    frames = []
    for code in ins_codes:
        try:
            rows = tsetmc.closing_price_daily_list(session, code)
        except DataUnavailable:
            continue
        if rows:
            frames.append(pd.DataFrame(rows))
    if not frames:
        return _empty_frame(["Last", "Value", "Count"])

    # the primary code is appended last so `keep="last"` lets it win on overlapping dates
    raw = pd.concat(frames, ignore_index=True)
    raw = raw.sort_values("dEven").drop_duplicates("dEven", keep="last")
    frame = pd.DataFrame(
        {
            "Open": raw["priceFirst"].astype("float64"),
            "High": raw["priceMax"].astype("float64"),
            "Low": raw["priceMin"].astype("float64"),
            "Close": raw["pClosing"].astype("float64"),
            "Last": raw["pDrCotVal"].astype("float64"),
            "Volume": raw["qTotTran5J"].astype("float64"),
            "Value": raw["qTotCap"].astype("float64"),
            "Count": raw["zTotTran"].astype("float64"),
        }
    )
    frame.index = pd.DatetimeIndex(
        [pd.Timestamp(deven_to_date(d)) for d in raw["dEven"]], name="Date"
    )
    frame = frame.sort_index()
    # non-trading calendar rows carry zero volume and zero trade count
    frame = frame[~((frame["Volume"] == 0) & (frame["Count"] == 0))]
    return frame[["Open", "High", "Low", "Close", "Volume", "Last", "Value", "Count"]]


def _index_daily(session: requests.Session, ins_code: str) -> pd.DataFrame:
    rows = tsetmc.index_history(session, ins_code)
    if not rows:
        return _empty_frame()
    raw = pd.DataFrame(rows).sort_values("dEven").drop_duplicates("dEven", keep="last")
    close = raw["xNivInuClMresIbs"].astype("float64")
    frame = pd.DataFrame(
        {
            "Open": close.values,
            "High": raw["xNivInuPhMresIbs"].astype("float64").values,
            "Low": raw["xNivInuPbMresIbs"].astype("float64").values,
            "Close": close.values,
            "Volume": np.nan,
        }
    )
    frame.index = pd.DatetimeIndex(
        [pd.Timestamp(deven_to_date(d)) for d in raw["dEven"]], name="Date"
    )
    return frame.sort_index()


def _tgju_daily(session: requests.Session, slug: str) -> pd.DataFrame:
    rows = tgju.history(session, slug)
    if not rows:
        return _empty_frame()
    frame = pd.DataFrame(
        [(o, h, low, c) for _, o, h, low, c in rows],
        columns=["Open", "High", "Low", "Close"],
        dtype="float64",
    )
    frame["Volume"] = np.nan
    frame.index = pd.DatetimeIndex([pd.Timestamp(day) for day, *_ in rows], name="Date")
    return frame[~frame.index.duplicated(keep="last")].sort_index()


def _crypto_daily(pair: str, start: Optional[_dt.date], interval: str) -> pd.DataFrame:
    from .sources import crypto  # local import: optional dependency

    rows = crypto.ohlcv(pair, since=start, timeframe=interval)
    if not rows:
        return _empty_frame()
    frame = pd.DataFrame(rows, columns=["ts", "Open", "High", "Low", "Close", "Volume"])
    index = pd.to_datetime(frame.pop("ts"), unit="ms")
    if interval == "1d":
        index = index.dt.floor("D")
    frame.index = pd.DatetimeIndex(index, name="Date")
    return frame.astype("float64").sort_index()


def _sci_monthly(session: requests.Session, alias: str) -> pd.DataFrame:
    """CPI is a single monthly level, so O=H=L=C and there is no volume.

    ``MoM``/``YoY`` are computed from the index itself rather than read from the
    workbook's own percent-change sheets, so the three columns can never disagree.
    """
    observations, _meta = sci.series(session, alias)
    if not observations:
        return _empty_frame(["MoM", "YoY"])
    level = pd.Series(
        [value for _, value in observations],
        index=pd.DatetimeIndex([pd.Timestamp(day) for day, _ in observations], name="Date"),
        dtype="float64",
    )
    frame = pd.DataFrame(
        {"Open": level, "High": level, "Low": level, "Close": level, "Volume": np.nan}
    )
    frame["MoM"] = level.pct_change() * 100.0
    frame["YoY"] = level.pct_change(12) * 100.0
    return frame


def fetch_daily(
    session: requests.Session,
    instrument: Instrument,
    *,
    start: Optional[_dt.date] = None,
    interval: str = "1d",
) -> pd.DataFrame:
    """Raw (unadjusted) OHLCV for any instrument kind, ascending by date."""
    if instrument.source == "crypto":
        return _crypto_daily(instrument.ins_code, start, interval)
    if instrument.source == "sci":
        return _sci_monthly(session, instrument.ins_code)
    if instrument.source == "tgju":
        return _tgju_daily(session, instrument.ins_code)
    if instrument.kind == "INDEX":
        return _index_daily(session, instrument.ins_code)
    codes = list(instrument.alt_ins_codes) + [instrument.ins_code]
    return _tsetmc_daily(session, codes)


def _adjust_events(session: requests.Session, ins_code: str) -> List[Tuple[_dt.date, float, float]]:
    """``(ex_date, adjusted_prev_close, unadjusted_prev_close)`` oldest first."""
    try:
        rows = tsetmc.price_adjust_list(session, ins_code)
    except DataUnavailable:
        return []
    events = []
    for row in rows or []:
        try:
            day = deven_to_date(row["dEven"])
        except (KeyError, ValueError, TypeError):
            continue
        prices = [
            float(value)
            for key, value in row.items()
            if key.lower().startswith("pclosing") and isinstance(value, (int, float))
        ]
        if len(prices) < 2:
            continue
        unadjusted, adjusted = max(prices), min(prices)
        if adjusted <= 0 or unadjusted <= 0:
            continue
        events.append((day, adjusted, unadjusted))
    events.sort(key=lambda e: e[0])
    return events


def _share_events(session: requests.Session, ins_code: str) -> List[Tuple[_dt.date, float, float]]:
    """``(date, shares_old, shares_new)`` oldest first, changes only."""
    try:
        rows = tsetmc.share_change(session, ins_code) or []
    except DataUnavailable:
        return []
    events = []
    for row in rows:
        try:
            day = deven_to_date(row["dEven"])
            old = float(row["numberOfShareOld"])
            new = float(row["numberOfShareNew"])
        except (KeyError, ValueError, TypeError):
            continue
        if old > 0 and new > 0 and new != old:
            events.append((day, old, new))
    events.sort(key=lambda e: e[0])
    return events


def _corporate_events(
    session: requests.Session, ins_code: str, *, infer_bonus: bool = True
) -> Tuple[List[Tuple[_dt.date, float]], pd.Series, pd.Series]:
    """``(price_ratios, dividends, splits)`` for one TSETMC instrument.

    ``price_ratios`` is ``(ex_date, factor)`` oldest first, one per event; every bar
    strictly before ``ex_date`` is multiplied by ``factor``. A TSETMC adjust row gives
    ``adjusted / unadjusted``. A share change that TSETMC did not adjust for (its list
    covers dividends and little else) is taken as a bonus issue: ``old / new``, unless
    ``infer_bonus`` is false, which is the case for funds: an ETF's unit count moves with
    every creation and redemption and says nothing about its price.
    """
    adjust = _adjust_events(session, ins_code)
    shares = _share_events(session, ins_code) if infer_bonus else []

    ratios: List[Tuple[_dt.date, float]] = []
    dividends, splits = {}, {}
    matched = set()
    for day, adjusted, unadjusted in adjust:
        ratios.append((day, adjusted / unadjusted))
        index = next(
            (
                i
                for i, (sday, _, _) in enumerate(shares)
                if i not in matched and abs((sday - day).days) <= 3
            ),
            None,
        )
        if index is None:
            dividends[pd.Timestamp(day)] = unadjusted - adjusted
        else:
            matched.add(index)
            _, old, new = shares[index]
            splits[pd.Timestamp(day)] = new / old
    for i, (day, old, new) in enumerate(shares):
        if i in matched:
            continue
        splits[pd.Timestamp(day)] = new / old
        ratios.append((day, old / new))
    ratios.sort(key=lambda e: e[0])

    return (
        ratios,
        pd.Series(dividends, dtype="float64", name="Dividends").sort_index(),
        pd.Series(splits, dtype="float64", name="Stock Splits").sort_index(),
    )


def fetch_actions(
    session: requests.Session, instrument: Instrument
) -> Tuple[pd.Series, pd.Series]:
    """``(dividends, splits)`` indexed by ex-date."""
    if not instrument.is_tsetmc or instrument.kind == "INDEX":
        return _EMPTY_ACTIONS[0].copy(), _EMPTY_ACTIONS[1].copy()
    _, dividends, splits = _corporate_events(
        session, instrument.ins_code, infer_bonus=instrument.kind != "ETF"
    )
    return dividends, splits


def _adjust_factors(index: pd.DatetimeIndex, ratios: List[Tuple[_dt.date, float]]) -> pd.Series:
    """Factor for every bar: product of the ratios of all *later* events."""
    factors = pd.Series(1.0, index=index, dtype="float64")
    for day, ratio in ratios:
        factors[index < pd.Timestamp(day)] *= ratio
    return factors


def _on_next_bar(index: pd.DatetimeIndex, actions: pd.Series) -> pd.Series:
    """``actions`` re-keyed to the first bar at or after each date; dates past the end drop."""
    out = pd.Series(0.0, index=index, dtype="float64")
    if len(actions):
        positions = index.searchsorted(actions.index)
        keep = positions < len(index)
        out.iloc[positions[keep]] = actions.values[keep]
    return out


def history(
    session: requests.Session,
    instrument: Instrument,
    *,
    period: str = "max",
    start=None,
    end=None,
    interval: str = "1d",
    auto_adjust: bool = True,
    actions: bool = False,
    jalali: bool = False,
) -> pd.DataFrame:
    if interval not in _ALLOWED_INTERVALS.get(instrument.source, {"1d"}):
        raise NotImplementedError(
            f"interval {interval!r} is not supported for a {instrument.source} instrument"
        )

    start_date = parse_date(start)
    end_date = parse_date(end)
    if start_date is None and end_date is None:
        start_date = period_start(period)

    frame = fetch_daily(session, instrument, start=start_date, interval=interval)
    extra = [c for c in ("Last", "Value", "Count", "MoM", "YoY") if c in frame.columns]

    if frame.empty:
        empty = _empty_frame(extra + (["Adj Close"] if not auto_adjust else []))
        return empty

    if instrument.is_tsetmc and instrument.kind != "INDEX":
        ratios, dividends, splits = _corporate_events(
            session, instrument.ins_code, infer_bonus=instrument.kind != "ETF"
        )
    else:
        ratios, dividends, splits = [], _EMPTY_ACTIONS[0].copy(), _EMPTY_ACTIONS[1].copy()

    price_columns = [c for c in ("Open", "High", "Low", "Close", "Last") if c in frame.columns]
    if ratios:
        factors = _adjust_factors(frame.index, ratios)
        if auto_adjust:
            for column in price_columns:
                frame[column] = frame[column] * factors
        else:
            frame["Adj Close"] = frame["Close"] * factors
    elif not auto_adjust:
        frame["Adj Close"] = frame["Close"]

    # an ex-date is often a halted (bar-less) day, so an action lands on the first bar
    # at or after it, where the adjusted price gap is visible
    frame["Dividends"] = _on_next_bar(frame.index, dividends)
    frame["Stock Splits"] = _on_next_bar(frame.index, splits)

    if start_date is not None:
        frame = frame[frame.index >= pd.Timestamp(start_date)]
    if end_date is not None:  # `end` is exclusive, like yfinance
        frame = frame[frame.index < pd.Timestamp(end_date)]

    columns = list(BASE_COLUMNS)
    if not auto_adjust and "Adj Close" in frame.columns:
        columns.insert(4, "Adj Close")
    columns += extra
    frame = frame[[c for c in columns if c in frame.columns]]

    if jalali:
        frame = frame.copy()
        frame["JDate"] = [to_jalali(ts) for ts in frame.index]
    return frame


def deven_range(start: Optional[_dt.date], end: Optional[_dt.date]) -> Tuple[int, int]:
    """Convenience for callers that need the TSETMC integer form of a window."""
    return (
        date_to_deven(start) if start else 0,
        date_to_deven(end) if end else 99991231,
    )
