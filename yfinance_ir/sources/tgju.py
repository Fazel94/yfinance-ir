"""TGJU (tgju.org) FX / gold / coin quotes.

Verified live (2026-09-20): the JSON history endpoint
``https://api.tgju.org/v1/market/indicator/summary-table-data/{slug}`` works for every
slug in :data:`ALIASES` (including the four coin slugs) and answers

``{"draw": "1", "recordsTotal": N, "data": [[open, low, high, close, <chg html>,
<pct html>, "YYYY/MM/DD", "jjjj/mm/dd"], ...]}``

with comma-grouped numbers and a **Gregorian** date in ``row[6]`` (slash separated, not
dashes). Prices are Rial. The ``chartData`` scrape of ``https://www.tgju.org/profile/{slug}``
is kept as a close-only fallback for when that endpoint changes.
"""

import json
import re
from datetime import date, datetime, timezone
from typing import List, Optional, Tuple

import requests

from .._http import get
from ..exceptions import DataUnavailable

__all__ = ["ALIASES", "API", "PROFILE", "catalog", "history", "profile_chart", "slug_for"]

API = "https://api.tgju.org/v1/market"
PROFILE = "https://www.tgju.org/profile"

#: human ticker -> tgju slug
ALIASES = {
    "USD": "price_dollar_rl",
    "EUR": "price_eur",
    "AED": "price_aed",
    "GBP": "price_gbp",
    "TRY": "price_try",
    "CNY": "price_cny",
    "CAD": "price_cad",
    "AUD": "price_aud",
    "GOLD18": "geram18",
    "GOLD24": "geram24",
    "MESGHAL": "mesghal",
    "ONS": "ons",
    "COIN": "sekee",
    "COIN_HALF": "nim",
    "COIN_QUARTER": "rob",
    "COIN_GRAM": "gerami",
}

_SLUG_RE = re.compile(r"^[a-z0-9_]+$")
_CHART_RE = re.compile(r"chartData:\s*(\[\[.*?\]\])", re.S)
_TAG_RE = re.compile(r"<[^>]+>")

Row = Tuple[date, float, float, float, float]


def slug_for(query: str) -> Optional[str]:
    """``"USD"`` -> ``"price_dollar_rl"``; a raw slug passes through; else ``None``."""
    upper = query.upper()
    if upper in ALIASES:
        return ALIASES[upper]
    if _SLUG_RE.match(query):
        return query
    return None


def catalog(session: requests.Session) -> List[dict]:
    payload = get(session, f"{API}/finder/list").json()
    if isinstance(payload, dict) and "response" in payload:
        return payload["response"].get("items") or []
    return payload if isinstance(payload, list) else []


def _number(text) -> Optional[float]:
    if text is None:
        return None
    clean = _TAG_RE.sub("", str(text)).replace(",", "").replace("%", "").strip()
    if not clean or clean in {"-", "--"}:
        return None
    try:
        return float(clean)
    except ValueError:
        return None


def history(session: requests.Session, slug: str, length: int = 100000) -> List[Row]:
    """Daily ``(date, open, high, low, close)`` rows, oldest first."""
    url = f"{API}/indicator/summary-table-data/{slug}"
    params = {"lang": "fa", "order_dir": "asc", "draw": 1, "start": 0, "length": length}
    try:
        payload = get(session, url, params=params).json()
        rows = payload.get("data") if isinstance(payload, dict) else None
    except (DataUnavailable, ValueError):
        rows = None
    if not isinstance(rows, list) or not rows:
        return profile_chart(session, slug)

    out: List[Row] = []
    for row in rows:
        if len(row) < 7:
            continue
        open_, low, high, close = (_number(row[i]) for i in range(4))
        day = _parse_day(row[6])
        if day is None or close is None:
            continue
        open_ = open_ if open_ is not None else close
        high = high if high is not None else close
        low = low if low is not None else close
        out.append((day, open_, high, low, close))
    out.sort(key=lambda r: r[0])
    return out


def _parse_day(text: str) -> Optional[date]:
    text = str(text).strip().replace("-", "/")
    try:
        return datetime.strptime(text, "%Y/%m/%d").date()
    except ValueError:
        return None


def profile_chart(session: requests.Session, slug: str) -> List[Row]:
    """Close-only fallback: scrape ``chartData`` out of the profile page HTML."""
    response = get(session, f"{PROFILE}/{slug}", expect_json=False)
    matches = _CHART_RE.findall(response.text)
    if not matches:
        raise DataUnavailable(response.status_code, f"{PROFILE}/{slug}", f"no chartData for {slug!r}")
    points = json.loads(matches[-1])
    out: List[Row] = []
    for point in points:
        if len(point) < 2:
            continue
        day = datetime.fromtimestamp(point[0] / 1000.0, timezone.utc).date()
        price = _number(point[1])
        if price is None:
            continue
        out.append((day, price, price, price, price))
    out.sort(key=lambda r: r[0])
    return out
