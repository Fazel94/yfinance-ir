"""Live smoke tests. Excluded by default; run with ``pytest -m live`` from an Iranian IP."""

import datetime as _dt

import pandas as pd
import pytest

import yfinance_ir as yf
from yfinance_ir.exceptions import DataUnavailable

pytestmark = pytest.mark.live


@pytest.fixture(autouse=True)
def live_config():
    yf.set_config(min_interval=0.2)
    yield
    yf.set_config(min_interval=0.1)


def test_equity_history_is_continuous_and_adjusted():
    ticker = yf.Ticker("فولاد")

    adjusted = ticker.history(period="1y")
    raw = ticker.history(period="1y", auto_adjust=False)

    assert len(adjusted) > 100
    assert adjusted.index.is_monotonic_increasing
    assert not adjusted.index.has_duplicates
    assert (adjusted["High"] >= adjusted["Low"]).all()
    assert (adjusted["Volume"] > 0).all()
    # the newest bar is never adjusted; older ones are, because فولاد pays a dividend
    assert adjusted["Close"].iloc[-1] == raw["Close"].iloc[-1]
    assert adjusted["Close"].iloc[0] < raw["Close"].iloc[0]


def test_equity_info_is_populated():
    info = yf.Ticker("فولاد").info

    assert info["isin"].startswith("IR")
    assert info["quoteType"] == "EQUITY"
    assert info["sharesOutstanding"] > 0
    assert info["regularMarketPrice"] > 0
    assert info["marketCap"] > info["regularMarketPrice"]


def test_index_and_tgju_series_reach_today():
    index = yf.Ticker("شاخص کل").history(period="1y")
    usd = yf.Ticker("USD").history(period="1y")

    for frame in (index, usd):
        assert len(frame) > 100
        age = _dt.date.today() - frame.index[-1].date()
        assert age.days < 15, f"stale series, last bar {frame.index[-1]}"
    assert pd.isna(index["Volume"]).all()


def test_etf_exposes_its_nav():
    info = yf.Ticker("اهرم").info

    assert info["quoteType"] == "ETF"
    assert info["navPrice"] > 0


def test_orderbook_and_client_types():
    ticker = yf.Ticker("فولاد")

    book = ticker.orderbook
    clients = ticker.client_type_history()

    assert len(book) == 5
    assert (book["bid_price"] <= book["ask_price"]).all()
    assert len(clients) > 100
    assert (
        clients["individual_buy_volume"] + clients["institutional_buy_volume"]
        == clients["individual_sell_volume"] + clients["institutional_sell_volume"]
    ).mean() > 0.9


def test_codal_income_statement():
    frame = yf.Ticker("فولاد").income_stmt

    assert not frame.empty
    assert isinstance(frame.columns[0], pd.Timestamp)
    assert frame.notna().any().any()


def test_codal_cash_flow_statement():
    frame = yf.Ticker("فولاد").cashflow

    assert isinstance(frame.columns[0], pd.Timestamp)
    assert any("نقد" in label and "عملیاتی" in label for label in frame.index)


def test_option_chain_of_an_etf():
    ticker = yf.Ticker("اهرم")

    expirations = ticker.options
    chain = ticker.option_chain()

    assert expirations and list(expirations) == sorted(expirations)
    assert len(chain.calls) == len(chain.puts) > 0
    assert (chain.calls["strike"] > 0).all()
    assert chain.underlying["regularMarketPrice"] > 0


def test_intraday_bars_add_up_to_the_daily_bar():
    ticker = yf.Ticker("فولاد")

    bars = ticker.history(period="5d", interval="5m", auto_adjust=False)
    daily = ticker.history(period="5d", auto_adjust=False)

    assert str(bars.index.tz) == "Asia/Tehran"
    clock = bars.index.hour * 100 + bars.index.minute
    assert clock.min() >= 900 and clock.max() <= 1230
    # a running session can be ahead of the daily list, so only finished days are compared
    today = _dt.date.today()
    volume = bars["Volume"].groupby(bars.index.date).sum()
    volume = volume[[day < today for day in volume.index]]
    finished = daily[daily.index.date < today]
    assert list(volume.index) == list(finished.index.date)
    assert list(volume) == list(finished["Volume"])


def test_cpi_series_is_monthly_and_current():
    cpi = yf.Ticker("CPI")

    frame = cpi.history(period="max")
    info = cpi.info

    assert len(frame) > 150  # published monthly since 1390
    assert frame.index.is_monotonic_increasing
    assert (frame["Close"].diff().dropna() > -frame["Close"].iloc[:-1].values * 0.5).all()
    # the latest release is at most a couple of months behind
    assert (_dt.date.today() - frame.index[-1].date()).days < 120
    assert info["baseYear"] == 1400
    assert 0 < info["annualInflation"] < 300
    assert yf.Ticker("CPI_RURAL").history(period="2y")["YoY"].notna().any()


def test_download_two_symbols():
    frame = yf.download(["فولاد", "فملی"], period="1mo", progress=False)

    assert frame.columns.names == ["Price", "Ticker"]
    assert frame[("Close", "فولاد")].notna().any()
    assert frame[("Close", "فملی")].notna().any()


def test_crypto_pair_if_ccxt_ir_is_installed():
    try:
        frame = yf.Ticker("BTC-IRT").history(period="1mo")
    except DataUnavailable as exc:
        pytest.skip(str(exc))
    assert len(frame) > 10
    assert (frame["High"] >= frame["Low"]).all()
