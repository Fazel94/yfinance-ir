"""Thin wrappers over ``cdn.tsetmc.com/api`` (plus two legacy ``old.tsetmc.com`` endpoints).

Every response is ``{"<camelCaseKey>": <payload>}``; :func:`_call` unwraps the single key.
No pandas here -- these return plain dicts/lists.

Endpoint shapes verified live (2026-09-20, Iranian egress):

* ``Instrument/GetInstrumentSearch/{q}`` -> ``instrumentSearch[]``. NOTE ``cIsin`` is
  always ``null`` in search results and ``lastDate`` is a flag, not a date, so ISIN and
  recency have to come from :func:`identity` / :func:`closing_price_info`. The
  ``insCode2/3/4`` fields are the wholesale ("فولاد2/3/4") boards of the same company,
  NOT historic listings -- never merge them into a price history.
* ``ClosingPrice/GetPriceAdjustList/{ins}`` -> ``priceAdjust[]`` with
  ``{dEven, pClosing, pClosingNotAdjusted}`` (confirmed, matches the planned names).
* ``Instrument/GetInstrumentShareChange/{ins}`` -> ``instrumentShareChange[]`` with
  ``{dEven, numberOfShareNew, numberOfShareOld}``.
* ``ClientType/GetClientType/{ins}/1/0`` returns volumes and counts only -- no values.
  The legacy ``old.tsetmc.com/tsev2/data/clienttype.aspx`` text feed has all 13 fields
  and is the only source of client-type *history*; it was verified working.
* Index history: the planned ``Index/GetIndexB1History`` 404s and the legacy
  ``chart/data/IndexFinancial.aspx`` returns an empty body. The working endpoint is
  ``Index/GetIndexB2History/{ins}`` -> ``indexB2[]`` with
  ``{dEven, xNivInuClMresIbs (close), xNivInuPbMresIbs (low), xNivInuPhMresIbs (high)}``,
  full history back to 2008.
"""

from typing import Any, List

import requests

from .._http import TSETMC_HEADERS, get

__all__ = [
    "BASE",
    "OLD_BASE",
    "TEDPIX_INS_CODE",
    "search",
    "identity",
    "info",
    "closing_price_daily_list",
    "closing_price_info",
    "best_limits",
    "client_type",
    "client_type_history_txt",
    "price_adjust_list",
    "share_change",
    "shareholders",
    "codal_prepared",
    "messages",
    "indices_all",
    "index_history",
    "etf",
    "market_overview",
]

BASE = "https://cdn.tsetmc.com/api"
OLD_BASE = "https://old.tsetmc.com"

#: شاخص کل (TEDPIX)
TEDPIX_INS_CODE = "32097828799138957"


def _call(session: requests.Session, path: str) -> Any:
    response = get(session, BASE + path, host_headers=TSETMC_HEADERS)
    payload = response.json()
    if isinstance(payload, dict) and len(payload) == 1:
        return next(iter(payload.values()))
    return payload


def _call_text(session: requests.Session, url: str) -> str:
    response = get(
        session,
        url,
        host_headers=dict(TSETMC_HEADERS, Accept="*/*"),
        expect_json=False,
    )
    return response.text


def search(session: requests.Session, query: str) -> List[dict]:
    return _call(session, f"/Instrument/GetInstrumentSearch/{query}") or []


def identity(session: requests.Session, ins_code: str) -> dict:
    return _call(session, f"/Instrument/GetInstrumentIdentity/{ins_code}") or {}


def info(session: requests.Session, ins_code: str) -> dict:
    return _call(session, f"/Instrument/GetInstrumentInfo/{ins_code}") or {}


def closing_price_daily_list(session: requests.Session, ins_code: str, top: int = 0) -> List[dict]:
    return _call(session, f"/ClosingPrice/GetClosingPriceDailyList/{ins_code}/{top}") or []


def closing_price_info(session: requests.Session, ins_code: str) -> dict:
    return _call(session, f"/ClosingPrice/GetClosingPriceInfo/{ins_code}") or {}


def best_limits(session: requests.Session, ins_code: str) -> List[dict]:
    return _call(session, f"/BestLimits/{ins_code}") or []


def client_type(session: requests.Session, ins_code: str) -> dict:
    return _call(session, f"/ClientType/GetClientType/{ins_code}/1/0") or {}


def client_type_history_txt(session: requests.Session, ins_code: str) -> str:
    """Legacy semicolon-separated client-type history (13 comma-separated fields per row)."""
    return _call_text(session, f"{OLD_BASE}/tsev2/data/clienttype.aspx?i={ins_code}")


def price_adjust_list(session: requests.Session, ins_code: str) -> List[dict]:
    return _call(session, f"/ClosingPrice/GetPriceAdjustList/{ins_code}") or []


def share_change(session: requests.Session, ins_code: str) -> List[dict]:
    return _call(session, f"/Instrument/GetInstrumentShareChange/{ins_code}") or []


def shareholders(session: requests.Session, ins_code: str, deven: int) -> List[dict]:
    return _call(session, f"/Shareholder/{ins_code}/{deven}") or []


def codal_prepared(session: requests.Session, ins_code: str, top: int = 20) -> List[dict]:
    return _call(session, f"/Codal/GetPreparedDataByInsCode/{top}/{ins_code}") or []


def messages(session: requests.Session, ins_code: str) -> List[dict]:
    return _call(session, f"/Msg/GetMsgByInsCode/{ins_code}") or []


def indices_all(session: requests.Session, flow: int = 1) -> List[dict]:
    """``flow`` 1 = بورس, 2 = فرابورس."""
    return _call(session, f"/Index/GetIndexB1LastAll/All/{flow}") or []


def index_history(session: requests.Session, ins_code: str) -> List[dict]:
    return _call(session, f"/Index/GetIndexB2History/{ins_code}") or []


def etf(session: requests.Session, ins_code: str) -> dict:
    """ETF/fund NAV block. Raises ``DataUnavailable`` (HTTP 500) for ordinary stocks."""
    return _call(session, f"/Fund/GetETFByInsCode/{ins_code}") or {}


def market_overview(session: requests.Session, flow: int = 1) -> dict:
    return _call(session, f"/MarketData/GetMarketOverview/{flow}") or {}
