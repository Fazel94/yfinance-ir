"""Offline test harness: every non-``live`` test runs against ``responses`` stubs.

``api`` is a small builder that registers TSETMC / TGJU / Codal routes with the exact
URLs the package uses, so a wrong path in :mod:`yfinance_ir.sources` fails the test
instead of silently hitting the network. Unmapped requests raise
``responses.ConnectionError``.
"""

import json
import os
import sys

import pytest
import responses
from responses import matchers

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yfinance_ir import _cache, set_config  # noqa: E402
from yfinance_ir._http import new_session  # noqa: E402
from yfinance_ir.sources import codal, tgju, tsetmc  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def load_fixture(name):
    path = os.path.join(FIXTURES, name)
    with open(path, encoding="utf-8") as handle:
        return json.load(handle) if name.endswith(".json") else handle.read()


@pytest.fixture(autouse=True)
def isolated_config(tmp_path):
    """Per-test sqlite cache, no throttling, no ambient proxy."""
    set_config(cache_dir=str(tmp_path / "cache"), min_interval=0.0, trust_env=False,
               crypto_exchange="nobitex")
    _cache.get_cache().clear()
    yield
    set_config(cache_dir=None, min_interval=0.1, trust_env=True)


class Api:
    """Registers the routes the package actually calls."""

    def __init__(self, mock):
        self.mock = mock

    def _json(self, url, payload, status=200, **kwargs):
        self.mock.add(responses.GET, url, json=payload, status=status, **kwargs)

    def _text(self, url, body, content_type="text/plain", status=200, **kwargs):
        self.mock.add(responses.GET, url, body=body, status=status, content_type=content_type, **kwargs)

    # ---------------------------------------------------------------- tsetmc
    def search(self, query, rows):
        self._json(f"{tsetmc.BASE}/Instrument/GetInstrumentSearch/{query}", {"instrumentSearch": rows})

    def identity(self, ins, **fields):
        payload = {
            "lVal18AFC": fields.pop("symbol", "فولاد"),
            "lVal30": fields.pop("name", "فولاد مبارکه اصفهان"),
            "cIsin": fields.pop("isin", "IRO1FOLD0009"),
            "flow": fields.pop("flow", 1),
            "cgrValCotTitle": fields.pop("market", "بازار اول (تابلوی اصلی) بورس"),
            "cgrValCot": fields.pop("group", "N1"),
        }
        payload.update(fields)
        self._json(f"{tsetmc.BASE}/Instrument/GetInstrumentIdentity/{ins}", {"instrumentIdentity": payload})

    def info(self, ins, **fields):
        self._json(f"{tsetmc.BASE}/Instrument/GetInstrumentInfo/{ins}", {"instrumentInfo": fields})

    def quote(self, ins, **fields):
        self._json(
            f"{tsetmc.BASE}/ClosingPrice/GetClosingPriceInfo/{ins}", {"closingPriceInfo": fields}
        )

    def daily(self, ins, rows):
        self._json(
            f"{tsetmc.BASE}/ClosingPrice/GetClosingPriceDailyList/{ins}/0",
            {"closingPriceDaily": rows},
        )

    def adjust(self, ins, rows):
        self._json(f"{tsetmc.BASE}/ClosingPrice/GetPriceAdjustList/{ins}", {"priceAdjust": rows})

    def share_change(self, ins, rows):
        self._json(
            f"{tsetmc.BASE}/Instrument/GetInstrumentShareChange/{ins}",
            {"instrumentShareChange": rows},
        )

    def indices(self, flow, rows):
        self._json(f"{tsetmc.BASE}/Index/GetIndexB1LastAll/All/{flow}", {"indexB1": rows})

    def index_history(self, ins, rows):
        self._json(f"{tsetmc.BASE}/Index/GetIndexB2History/{ins}", {"indexB2": rows})

    def trade_history(self, ins, deven, rows, status=200):
        """Registered once per call; several registrations answer in order, the last repeats."""
        self._json(
            f"{tsetmc.BASE}/Trade/GetTradeHistory/{ins}/{deven}/false", {"tradeHistory": rows}, status=status
        )

    def trades(self, ins, rows, status=200):
        self._json(f"{tsetmc.BASE}/Trade/GetTrade/{ins}", {"trade": rows}, status=status)

    def option_watch(self, rows, flow=0):
        self._json(
            f"{tsetmc.BASE}/Instrument/GetInstrumentOptionMarketWatch/{flow}",
            {"instrumentOptMarketWatch": rows},
        )

    def equity(self, ins, *, symbol, rows, adjust=(), shares=(), name="نام شرکت"):
        """The full route set one TSETMC equity needs for search + history."""
        self.identity(ins, symbol=symbol, name=name)
        self.daily(ins, rows)
        self.adjust(ins, list(adjust))
        self.share_change(ins, list(shares))

    # ------------------------------------------------------------------ tgju
    def tgju_summary(self, slug, rows=None, status=200):
        url = f"{tgju.API}/indicator/summary-table-data/{slug}"
        if rows is None:
            self._text(url, "nope", status=status)
        else:
            self._json(url, {"data": rows}, status=status)

    def tgju_profile(self, slug, html):
        self._text(f"{tgju.PROFILE}/{slug}", html, content_type="text/html")

    # ----------------------------------------------------------------- codal
    def codal_search(self, letters, page=1):
        self._json(codal.SEARCH_URL, {"Total": len(letters), "Page": page, "Letters": letters})

    def codal_page(self, url, datasource, sheet_id=None):
        body = "<html><body><script>\nvar datasource = %s;\n</script></body></html>" % json.dumps(
            datasource, ensure_ascii=False
        )
        match = []
        if sheet_id is not None:
            match = [matchers.query_param_matcher({"SheetId": str(sheet_id)}, strict_match=False)]
        self._text(codal.BASE + url.split("?")[0], body, content_type="text/html; charset=utf-8", match=match)


@pytest.fixture
def api():
    with responses.RequestsMock(assert_all_requests_are_fired=False) as mock:
        yield Api(mock)


@pytest.fixture
def session():
    return new_session()
