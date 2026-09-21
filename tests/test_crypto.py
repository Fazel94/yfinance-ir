import sys
import types

import pandas as pd
import pytest

from yfinance_ir.exceptions import DataUnavailable, SymbolNotFound
from yfinance_ir.sources import crypto


class FakeExchange:
    """Minimal stand-in for a ccxt-ir exchange client."""

    id = "nobitex"

    def __init__(self, _options=None):
        self.has = {"fetchOHLCV": True}
        self.pages = 0

    def load_markets(self):
        return {"BTC/IRT": {}, "ETH/IRT": {}}

    def fetch_ohlcv(self, symbol, timeframe, since, limit):
        self.pages += 1
        if self.pages > 2:
            return []
        base = since
        return [[base + i * 86_400_000, 1.0, 2.0, 0.5, 1.5, 10.0] for i in range(limit)]

    def fetch_ticker(self, symbol):
        return {"last": 100.0, "bid": 99.0, "ask": 101.0, "high": 110.0, "low": 90.0,
                "open": 95.0, "baseVolume": 7.0, "previousClose": 94.0}

    def fetch_order_book(self, symbol, limit=5):
        return {"bids": [[99.0, 1.0], [98.0, 2.0]], "asks": [[101.0, 3.0]]}


@pytest.fixture
def fake_ccxt(monkeypatch):
    module = types.ModuleType("ccxt")
    module.nobitex = FakeExchange
    monkeypatch.setitem(sys.modules, "ccxt", module)
    crypto._exchanges.clear()
    yield module
    crypto._exchanges.clear()


def test_pair_is_translated_to_a_ccxt_symbol():
    assert crypto.to_ccxt_symbol("BTC-IRT") == "BTC/IRT"
    assert crypto.to_ccxt_symbol("btc-usdt") == "BTC/USDT"


def test_ohlcv_pages_until_the_exchange_stops_and_dedupes(fake_ccxt):
    rows = crypto.ohlcv("BTC-IRT", limit=5)

    assert len(rows) == 10  # two full pages, then an empty one stops the loop
    assert rows == sorted(rows, key=lambda row: row[0])
    assert len({row[0] for row in rows}) == len(rows)


def test_ticker_info_uses_the_yfinance_key_names(fake_ccxt):
    info = crypto.ticker_info("BTC-IRT")

    assert info["regularMarketPrice"] == 100.0
    assert info["quoteType"] == "CRYPTOCURRENCY"
    assert info["currency"] == "IRT"
    assert info["exchange"] == "nobitex"


def test_orderbook_pads_the_shorter_side(fake_ccxt):
    columns = ["bid_count", "bid_volume", "bid_price", "ask_price", "ask_volume", "ask_count"]

    book = crypto.orderbook("BTC-IRT", columns)

    assert list(book.columns) == columns
    assert len(book) == 2
    assert book.loc[1, "bid_price"] == 99.0
    assert pd.isna(book.loc[2, "ask_price"])  # the short side is padded, not truncated


def test_an_unlisted_pair_raises_symbol_not_found(fake_ccxt):
    with pytest.raises(SymbolNotFound):
        crypto.ticker_info("DOGE-IRT")


class BrokenExchange(FakeExchange):
    """ccxt-ir 4.19.0: fetch_ohlcv/fetch_order_book raise on every exchange."""

    urls = {"api": {"public": "https://apiv2.nobitex.ir"}}

    def market(self, symbol):
        base, _, quote = symbol.partition("/")
        return {"base": base, "quote": quote, "id": f"{base.lower()}-rls"}

    def fetch_ohlcv(self, *args, **kwargs):
        raise NameError("name 'Date' is not defined")

    def fetch_order_book(self, *args, **kwargs):
        raise TypeError("unsupported operand type(s) for /: 'str' and 'int'")


@pytest.fixture
def broken_ccxt(monkeypatch):
    module = types.ModuleType("ccxt")
    module.nobitex = BrokenExchange
    monkeypatch.setitem(sys.modules, "ccxt", module)
    crypto._exchanges.clear()
    yield module
    crypto._exchanges.clear()


def test_ohlcv_falls_back_to_the_nobitex_udf_feed(broken_ccxt, api):
    api.mock.add(
        "GET",
        "https://apiv2.nobitex.ir/market/udf/history",
        json={"s": "ok", "t": [1787000000, 1787086400], "o": [1, 2], "h": [3, 4],
              "l": [0.5, 1.5], "c": [2, 3], "v": [10, 20]},
    )

    rows = crypto.ohlcv("BTC-IRT")

    assert [row[0] for row in rows] == [1787000000000, 1787086400000]
    assert rows[0][1:] == [1.0, 3.0, 0.5, 2.0, 10.0]
    assert "symbol=BTCIRT" in api.mock.calls[0].request.url  # not ccxt's `btc-rls` id


def test_orderbook_falls_back_and_converts_rial_to_toman(broken_ccxt, api):
    api.mock.add(
        "GET",
        "https://apiv2.nobitex.ir/v3/orderbook/BTCIRT",
        json={"bids": [["185500000000", "0.01"]], "asks": [["185700000000", "0.02"]]},
    )

    book = crypto.orderbook("BTC-IRT", ["bid_count", "bid_volume", "bid_price",
                                        "ask_price", "ask_volume", "ask_count"])

    # /v3 quotes Rial; fetch_ticker and the UDF history quote Toman
    assert book.loc[1, "bid_price"] == 18_550_000_000.0
    assert book.loc[1, "ask_price"] == 18_570_000_000.0


def test_a_non_nobitex_exchange_reraises_the_ccxt_bug(monkeypatch):
    class Wallex(BrokenExchange):
        id = "wallex"

    module = types.ModuleType("ccxt")
    module.wallex = Wallex
    monkeypatch.setitem(sys.modules, "ccxt", module)
    crypto._exchanges.clear()
    from yfinance_ir.config import set_config

    set_config(crypto_exchange="wallex")
    with pytest.raises(NameError):
        crypto.ohlcv("BTC-IRT")


def test_missing_ccxt_ir_explains_the_extra(monkeypatch):
    monkeypatch.setitem(sys.modules, "ccxt", None)
    crypto._exchanges.clear()

    with pytest.raises(DataUnavailable, match=r"yfinance-ir\[crypto\]"):
        crypto.ticker_info("BTC-IRT")
