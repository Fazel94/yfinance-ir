import logging

import pandas as pd
import pytest

from yfinance_ir import download
from yfinance_ir.ticker import Tickers


def _bar(deven, close):
    return {
        "dEven": deven,
        "priceFirst": close,
        "priceMax": close,
        "priceMin": close,
        "pClosing": close,
        "pDrCotVal": close,
        "qTotTran5J": 100,
        "qTotCap": 100 * close,
        "zTotTran": 5,
    }


BARS = [_bar(20240101, 100), _bar(20240102, 110)]


@pytest.fixture
def two_symbols(api):
    for symbol, ins, price in (("فولاد", "222", 100), ("فملی", "333", 700)):
        api.search(symbol, [{"insCode": ins, "lVal18AFC": symbol, "lVal30": symbol}])
        api.equity(ins, symbol=symbol, rows=[_bar(20240101, price), _bar(20240102, price + 10)])
    return api


def test_download_returns_a_price_major_multiindex(two_symbols):
    frame = download(["فولاد", "فملی"], period="max", progress=False, threads=False)

    assert isinstance(frame.columns, pd.MultiIndex)
    assert frame.columns.names == ["Price", "Ticker"]
    assert frame[("Close", "فولاد")].iloc[0] == 100
    assert frame[("Close", "فملی")].iloc[0] == 700


def test_group_by_ticker_flips_the_levels(two_symbols):
    frame = download("فولاد فملی", period="max", group_by="ticker", progress=False, threads=False)

    assert frame.columns.names == ["Ticker", "Price"]
    assert frame[("فملی", "Close")].iloc[1] == 710


def test_a_single_symbol_keeps_the_flat_layout(two_symbols):
    frame = download("فولاد", period="max", progress=False, threads=False)

    assert not isinstance(frame.columns, pd.MultiIndex)
    assert "Close" in frame.columns


def test_a_failing_symbol_is_logged_and_dropped(api, caplog):
    api.search("فولاد", [{"insCode": "222", "lVal18AFC": "فولاد", "lVal30": "فولاد"}])
    api.equity("222", symbol="فولاد", rows=BARS)
    api.search("ندارد", [])
    api.indices(1, [])
    api.indices(2, [])

    with caplog.at_level(logging.WARNING, logger="yfinance_ir"):
        frame = download(["فولاد", "ندارد"], period="max", progress=False, threads=False)

    # the requested shape is kept (like yfinance), minus the symbol that failed
    assert list(frame.columns.get_level_values("Ticker").unique()) == ["فولاد"]
    assert "ندارد" in caplog.text


def test_every_symbol_failing_returns_an_empty_frame(api):
    api.search("ندارد", [])
    api.indices(1, [])
    api.indices(2, [])

    assert download(["ندارد"], period="max", progress=False, threads=False).empty


def test_tickers_bundle_shares_one_session_and_dedupes(two_symbols):
    bundle = Tickers("فولاد فملی فولاد")

    assert bundle.symbols == ["فولاد", "فملی"]
    assert bundle.tickers["فملی"].instrument.ins_code == "333"
    assert bundle.tickers["فولاد"].session is bundle.session
