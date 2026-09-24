"""Codal financial statements as yfinance-shaped wide DataFrames.

Layout of the embedded ``datasource`` (verified on فولاد, ``LetterType=6``, ``SheetId=1``):

``datasource.sheets[].tables[].cells[]`` where every cell carries ``rowSequence``,
``columnSequence``, ``value``, ``cellGroupName`` (``Header``/``Body``) and, for the
period columns only, ``periodEndToDate``/``yearEndToDate`` as Jalali ``YYYY/MM/DD``.
Column 1 holds the Persian line-item labels; the percentage-change columns have an empty
``periodEndToDate`` and are dropped. Numbers arrive as plain signed integers (no comma
grouping inside ``datasource``), but comma-grouped and ``(1,234)``-negative forms are
accepted too. A restated prior-period column can be all zeros next to the real one, so
for a duplicated period the column carrying more non-zero cells wins.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

import jdatetime
import pandas as pd
import requests

from .exceptions import DataUnavailable
from .resolver import normalize
from .sources import codal

__all__ = ["statements", "monthly_activity", "parse_datasource"]

_log = logging.getLogger("yfinance_ir")

_JDATE_RE = re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})$")


def _jalali_to_timestamp(text: str) -> Optional[pd.Timestamp]:
    text = codal.fa_digits(str(text or "")).strip()
    match = _JDATE_RE.match(text)
    if not match:
        return None
    year, month, day = (int(g) for g in match.groups())
    try:
        return pd.Timestamp(jdatetime.date(year, month, day).togregorian())
    except ValueError:
        return None


def _number(value) -> Optional[float]:
    if value is None:
        return None
    text = codal.fa_digits(str(value)).strip().replace(",", "")
    if not text or text in {"-", "--"}:
        return None
    negative = text.startswith("(") and text.endswith(")")
    if negative:
        text = text[1:-1]
    try:
        number = float(text)
    except ValueError:
        return None
    return -number if negative else number


def _pick_table(datasource: dict) -> List[dict]:
    best: List[dict] = []
    for sheet in datasource.get("sheets") or []:
        for table in sheet.get("tables") or []:
            cells = table.get("cells") or []
            if len(cells) > len(best):
                best = cells
    return best


def parse_datasource(datasource: dict) -> pd.DataFrame:
    """One Codal statement -> DataFrame(index=line item, columns=period end Timestamp)."""
    cells = _pick_table(datasource)
    if not cells:
        return pd.DataFrame()

    label_column = min((c.get("columnSequence") or 1) for c in cells)
    labels: Dict[int, str] = {}
    periods: Dict[int, pd.Timestamp] = {}
    values: Dict[Tuple[int, int], float] = {}

    for cell in cells:
        row = cell.get("rowSequence")
        column = cell.get("columnSequence")
        if row is None or column is None:
            continue
        period = _jalali_to_timestamp(cell.get("periodEndToDate"))
        if period is not None:
            periods.setdefault(column, period)
        if column == label_column:
            text = normalize(cell.get("value"), strip_zwnj=False)
            if text and _number(text) is None:
                labels[row] = text
            continue
        number = _number(cell.get("value"))
        if number is not None:
            values[(row, column)] = number

    if not labels or not periods:
        return pd.DataFrame()

    # a period can appear twice (restated vs. original); keep the richer column
    by_period: Dict[pd.Timestamp, int] = {}
    for column, period in periods.items():
        filled = sum(1 for (r, c), v in values.items() if c == column and v != 0)
        current = by_period.get(period)
        if current is None:
            by_period[period] = column
        else:
            current_filled = sum(1 for (r, c), v in values.items() if c == current and v != 0)
            if filled > current_filled:
                by_period[period] = column

    data = {}
    for period, column in by_period.items():
        data[period] = {label: values.get((row, column)) for row, label in labels.items()}
    frame = pd.DataFrame(data)
    frame = frame.reindex([labels[row] for row in sorted(labels) if labels[row] in frame.index])
    frame = frame[~frame.index.duplicated(keep="first")]
    frame = frame.dropna(how="all")  # section headers carry no numbers
    return frame.reindex(sorted(frame.columns, reverse=True), axis=1)


def _publish_key(letter: dict) -> str:
    return codal.fa_digits(letter.get("PublishDateTime") or letter.get("SentDateTime") or "")


def _default_window(years: int = 5) -> Tuple[str, str]:
    today = jdatetime.date.today()
    return f"{today.year - years:04d}/01/01", f"{today.year:04d}/12/29"


def _collect(
    session: requests.Session,
    letters: List[dict],
    sheet_id: Optional[int],
    max_letters: int,
) -> pd.DataFrame:
    letters = sorted(letters, key=_publish_key, reverse=True)[:max_letters]
    columns: Dict[pd.Timestamp, pd.Series] = {}
    order: List[str] = []
    for letter in letters:
        url = letter.get("Url")
        if not url:
            continue
        try:
            datasource = codal.datasource(session, url, sheet_id)
        except (DataUnavailable, ValueError) as exc:
            _log.warning("codal: cannot read %s (%s)", url, exc)
            continue
        frame = parse_datasource(datasource)
        if frame.empty:
            _log.warning("codal: no parseable table in %s", url)
            continue
        for label in frame.index:
            if label not in order:
                order.append(label)
        for period in frame.columns:
            # letters are newest-first, so the first writer of a period is the latest filing
            columns.setdefault(period, frame[period])
    if not columns:
        return pd.DataFrame()
    result = pd.DataFrame(columns).reindex(order)
    return result.reindex(sorted(result.columns, reverse=True), axis=1)


def statements(
    session: requests.Session,
    symbol: str,
    sheet_id: int = codal.SHEET_INCOME,
    *,
    from_jdate: Optional[str] = None,
    to_jdate: Optional[str] = None,
    quarterly: bool = False,
    max_letters: int = 8,
) -> pd.DataFrame:
    """Balance sheet, income statement or cash flow: ``codal.SHEET_BALANCE``/``_INCOME``/``_CASHFLOW``."""
    window = _default_window()
    letters = codal.letters(
        session,
        symbol,
        category=codal.CATEGORY_FINANCIAL,
        letter_type=codal.LETTER_INTERIM_FS,
        from_jdate=from_jdate or window[0],
        to_jdate=to_jdate or window[1],
    )
    if not letters:
        raise DataUnavailable(404, codal.SEARCH_URL, f"no Codal filings for {symbol!r}")
    annual = [letter for letter in letters if _is_annual(letter)]
    selected = letters if quarterly else (annual or letters)
    return _collect(session, selected, sheet_id, max_letters)


def _is_annual(letter: dict) -> bool:
    title = codal.fa_digits(letter.get("Title") or "")
    return "سال مالی" in title or "12 ماهه" in title


def monthly_activity(
    session: requests.Session,
    symbol: str,
    *,
    from_jdate: Optional[str] = None,
    to_jdate: Optional[str] = None,
    max_letters: int = 12,
) -> pd.DataFrame:
    window = _default_window(years=2)
    letters = codal.letters(
        session,
        symbol,
        category=codal.CATEGORY_MONTHLY,
        letter_type=codal.LETTER_MONTHLY,
        from_jdate=from_jdate or window[0],
        to_jdate=to_jdate or window[1],
    )
    if not letters:
        raise DataUnavailable(404, codal.SEARCH_URL, f"no monthly filings for {symbol!r}")
    return _collect(session, letters, None, max_letters)
