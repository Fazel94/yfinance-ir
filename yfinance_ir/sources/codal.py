"""Codal (codal.ir) filing search + embedded statement datasource.

Verified live (2026-09-20):

* ``GET https://search.codal.ir/api/search/v2/q`` with PascalCase params answers
  ``{"Total": int, "Page": int, "Letters": [...], "IsAttacker": bool}``. ``Page`` is the
  page *count*, so pagination loops ``PageNumber`` 1..Page.
* A letter's ``Url`` is a relative ``/Reports/Decision.aspx?LetterSerial=...`` path; adding
  ``&SheetId=<n>`` and GETting it on ``www.codal.ir`` returns HTML with an embedded
  ``var datasource = {...};`` blob (``sheets[].tables[].cells[]``).
* ``PublishDateTime``/``SentDateTime`` come back with **Persian digits**
  (``۱۴۰۵/۰۵/۰۷ ۲۰:۱۷:۰۱``) -- use :func:`fa_digits` before comparing or parsing them.
* ``SheetId`` 0 is صورت وضعیت مالی, 1 صورت سود و زیان and 9 صورت جریان های نقدی (checked
  2026-09-24 on فولاد, فملی and شپنا, annual and 3-month filings); 2-8 and 10-11 carry no
  datasource.
"""

import json
import re
from typing import List, Optional

import requests

from .._http import get
from ..exceptions import DataUnavailable

__all__ = [
    "SEARCH_URL",
    "BASE",
    "CATEGORY_FINANCIAL",
    "CATEGORY_MONTHLY",
    "LETTER_INTERIM_FS",
    "LETTER_FUND_PORTFOLIO",
    "LETTER_MONTHLY",
    "SHEET_BALANCE",
    "SHEET_INCOME",
    "SHEET_CASHFLOW",
    "fa_digits",
    "letters",
    "datasource",
]

SEARCH_URL = "https://search.codal.ir/api/search/v2/q"
BASE = "https://www.codal.ir"

CATEGORY_FINANCIAL = 1
CATEGORY_MONTHLY = 3
LETTER_INTERIM_FS = 6
LETTER_FUND_PORTFOLIO = 8
LETTER_MONTHLY = 58
SHEET_BALANCE = 0
SHEET_INCOME = 1
SHEET_CASHFLOW = 9

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_DATASOURCE_RE = re.compile(r"var\s+datasource\s*=\s*(\{.*?\})\s*;\s*$", re.S | re.M)


def fa_digits(text: str) -> str:
    """Persian/Arabic-Indic digits -> ASCII."""
    return (text or "").translate(_PERSIAN_DIGITS)


def letters(
    session: requests.Session,
    symbol: str,
    *,
    category: int = CATEGORY_FINANCIAL,
    letter_type: int = LETTER_INTERIM_FS,
    from_jdate: str = "1395/01/01",
    to_jdate: str = "1499/12/29",
    length: int = -1,
    max_pages: int = 20,
) -> List[dict]:
    """All matching letters, following ``PageNumber`` pagination."""
    out: List[dict] = []
    page = 1
    while page <= max_pages:
        params = {
            "Symbol": symbol,
            "Category": category,
            "PublisherType": 1,
            "LetterType": letter_type,
            "Length": length,
            "Audited": "true",
            "NotAudited": "true",
            "Mains": "true",
            "Childs": "false",
            "Consolidatable": "true",
            "NotConsolidatable": "true",
            "AuditorRef": -1,
            "CompanyState": 0,
            "CompanyType": -1,
            "PageNumber": page,
            "TracingNo": -1,
            "Publisher": "false",
            "IsNotAudited": "false",
            "FromDate": from_jdate,
            "ToDate": to_jdate,
        }
        payload = get(session, SEARCH_URL, params=params).json()
        batch = payload.get("Letters") or []
        out.extend(batch)
        total_pages = int(payload.get("Page") or 1)
        if page >= total_pages or not batch:
            break
        page += 1
    return out


def datasource(session: requests.Session, letter_url: str, sheet_id: Optional[int] = None) -> dict:
    """Parse the ``var datasource = {...};`` blob out of a Codal statement page."""
    url = letter_url if letter_url.startswith("http") else BASE + letter_url
    params = {"SheetId": sheet_id} if sheet_id is not None else None
    response = get(session, url, params=params, expect_json=False)
    match = _DATASOURCE_RE.search(response.text)
    if not match:
        raise DataUnavailable(response.status_code, url, f"no embedded datasource at {url}")
    return json.loads(match.group(1))
