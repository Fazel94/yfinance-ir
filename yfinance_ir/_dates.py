"""Date helpers: TSETMC ``dEven`` ints, Jalali conversion, yfinance ``period`` strings."""

import datetime as _dt
import re
from typing import Optional, Union

import jdatetime
import pandas as pd

__all__ = [
    "deven_to_date",
    "date_to_deven",
    "to_jalali",
    "parse_date",
    "parse_period",
    "period_start",
]

DateLike = Union[str, int, _dt.date, _dt.datetime, pd.Timestamp, None]

_PERIOD_DAYS = {
    "1d": 1,
    "5d": 5,
    "1mo": 31,
    "3mo": 92,
    "6mo": 183,
    "1y": 366,
    "2y": 731,
    "5y": 1827,
    "10y": 3653,
}

_DATE_RE = re.compile(r"^(\d{4})[-/](\d{1,2})[-/](\d{1,2})$")


def deven_to_date(deven: Union[int, str]) -> _dt.date:
    value = int(deven)
    return _dt.date(value // 10000, (value // 100) % 100, value % 100)


def date_to_deven(day: _dt.date) -> int:
    return day.year * 10000 + day.month * 100 + day.day


def to_jalali(day) -> str:
    if isinstance(day, pd.Timestamp):
        day = day.date()
    elif isinstance(day, _dt.datetime):
        day = day.date()
    jd = jdatetime.date.fromgregorian(date=day)
    return f"{jd.year:04d}-{jd.month:02d}-{jd.day:02d}"


def parse_date(value: DateLike) -> Optional[_dt.date]:
    """Accept ``date``/``datetime``/``Timestamp``/``YYYY-MM-DD``/Jalali ``1403-01-01``/``dEven``."""
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return value.date()
    if isinstance(value, _dt.datetime):
        return value.date()
    if isinstance(value, _dt.date):
        return value
    if isinstance(value, int):
        return deven_to_date(value) if value > 10000000 else None
    text = str(value).strip()
    match = _DATE_RE.match(text)
    if not match:
        if re.fullmatch(r"\d{8}", text):
            return deven_to_date(text)
        raise ValueError(f"unrecognised date: {value!r}")
    year, month, day = (int(g) for g in match.groups())
    if year < 1700:  # Jalali
        return jdatetime.date(year, month, day).togregorian()
    return _dt.date(year, month, day)


def parse_period(period: str) -> Optional[_dt.timedelta]:
    """``None`` means "everything" (``max``/``ytd`` are handled by :func:`period_start`)."""
    if period is None:
        return None
    key = str(period).lower()
    if key in {"max", "ytd"}:
        return None
    if key not in _PERIOD_DAYS:
        raise ValueError(f"unsupported period: {period!r}")
    return _dt.timedelta(days=_PERIOD_DAYS[key])


def period_start(period: str, today: Optional[_dt.date] = None) -> Optional[_dt.date]:
    today = today or _dt.date.today()
    key = str(period).lower() if period else "max"
    if key == "max":
        return None
    if key == "ytd":
        jnow = jdatetime.date.fromgregorian(date=today)
        return jdatetime.date(jnow.year, 1, 1).togregorian()
    delta = parse_period(key)
    return today - delta if delta else None
