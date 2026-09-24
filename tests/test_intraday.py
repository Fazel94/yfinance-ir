import pandas as pd
import pytest
from conftest import load_fixture

from yfinance_ir import intraday
from yfinance_ir.exceptions import DataUnavailable
from yfinance_ir.ticker import Ticker

INS = "222"
TEHRAN = "Asia/Tehran"


@pytest.fixture(autouse=True)
def no_retry_pause(monkeypatch):
    monkeypatch.setattr(intraday, "RETRY_DELAY", 0.0)


def _bar(deven, close, *, count=10, volume=1000):
    return {
        "dEven": deven,
        "priceFirst": close,
        "priceMax": close,
        "priceMin": close,
        "pClosing": close,
        "pDrCotVal": close,
        "qTotTran5J": volume,
        "qTotCap": close * volume,
        "zTotTran": count,
    }


def _trade(n, hms, price, volume, *, canceled=0):
    return {"insCode": None, "dEven": 0, "nTran": n, "hEven": hms, "qTitTran": volume,
            "pTran": float(price), "qTitNgJ": 0, "iSensVarP": "\u0000", "pPhSeaCotJ": 0.0,
            "pPbSeaCotJ": 0.0, "iAnuTran": 0, "xqVarPJDrPRf": 0.0, "canceled": canceled}


def _folad(api, bars, *, adjust=(), shares=(), latest=20240101, latest_count=0):
    """``latest`` is the session ``GetClosingPriceInfo`` reports, fetched through ``GetTrade``."""
    api.search("فولاد", [{"insCode": INS, "lVal18AFC": "فولاد", "lVal30": "فولاد"}])
    api.equity(INS, symbol="فولاد", rows=bars, adjust=adjust, shares=shares)
    api.quote(INS, dEven=latest, zTotTran=latest_count)
    return Ticker("فولاد")


def _at(text):
    return pd.Timestamp(text, tz=TEHRAN)


def test_trades_become_bars_on_the_tehran_clock(api):
    ticker = _folad(
        api,
        [_bar(20240929, 100, count=4), _bar(20240930, 0, count=0, volume=0), _bar(20241001, 101, count=1)],
    )
    # TSETMC answers newest first and not strictly sorted; 2024-09-30 did not trade and has no route
    api.trade_history(INS, 20240929, [
        _trade(4, 90500, 101, 2),
        _trade(2, 90300, 105, 5),
        _trade(3, 90459, 95, 1),
        _trade(1, 90005, 100, 10),
    ])
    api.trade_history(INS, 20241001, [_trade(1, 91000, 101, 7)])

    frame = ticker.history(start="2024-09-29", end="2024-10-02", interval="5m")

    assert frame.index.name == "Datetime"
    assert list(frame.index) == [_at("2024-09-29 09:00"), _at("2024-09-29 09:05"), _at("2024-10-01 09:10")]
    assert list(frame.columns) == [
        "Open", "High", "Low", "Close", "Volume", "Dividends", "Stock Splits", "Value", "Count"
    ]
    first = frame.iloc[0]
    assert (first["Open"], first["High"], first["Low"], first["Close"]) == (100, 105, 95, 95)
    assert (first["Volume"], first["Value"], first["Count"]) == (16, 100 * 10 + 105 * 5 + 95 * 1, 3)


def test_cancelled_trades_do_not_count(api):
    ticker = _folad(api, [_bar(20240929, 100, count=1)])
    api.trade_history(INS, 20240929, [_trade(1, 90000, 100, 10), _trade(2, 90100, 200, 99, canceled=1)])

    frame = ticker.history(start="2024-09-29", end="2024-09-30", interval="5m")

    assert (frame["High"].iloc[0], frame["Volume"].iloc[0], frame["Count"].iloc[0]) == (100, 10, 1)


def test_a_trade_listed_twice_counts_once(api):
    # one TSETMC backend repeats rows: فولاد 2026-09-19 came back with 78,339 rows for 78,299 trades
    ticker = _folad(api, [_bar(20240929, 100, count=2)])
    api.trade_history(
        INS, 20240929, [_trade(1, 90000, 100, 10), _trade(2, 90100, 101, 5), _trade(2, 90100, 101, 5)]
    )

    frame = ticker.history(start="2024-09-29", end="2024-09-30", interval="5m")

    assert (frame["Volume"].iloc[0], frame["Count"].iloc[0]) == (15, 2)


@pytest.mark.parametrize(
    "interval, starts",
    [
        ("1m", ["10:29", "10:30", "12:29"]),
        ("90m", ["09:00", "10:30", "12:00"]),
        ("1h", ["10:00", "12:00"]),
    ],
)
def test_a_trade_belongs_to_the_bar_its_time_floors_to(api, interval, starts):
    ticker = _folad(api, [_bar(20240929, 100, count=3)])
    api.trade_history(
        INS, 20240929, [_trade(1, 102959, 100, 1), _trade(2, 103000, 100, 1), _trade(3, 122959, 100, 1)]
    )

    frame = ticker.history(start="2024-09-29", end="2024-09-30", interval=interval)

    assert list(frame.index) == [_at(f"2024-09-29 {hm}") for hm in starts]


def test_a_day_is_retried_through_500s_and_empty_answers(api):
    ticker = _folad(api, [_bar(20240929, 100, count=1)])
    api.trade_history(INS, 20240929, [], status=500)
    api.trade_history(INS, 20240929, [])
    api.trade_history(INS, 20240929, [_trade(1, 90000, 100, 10)])

    frame = ticker.history(start="2024-09-29", end="2024-09-30", interval="5m")

    assert frame["Volume"].sum() == 10


def test_a_day_that_never_answers_raises_instead_of_leaving_a_gap(api):
    ticker = _folad(api, [_bar(20240929, 100, count=1)])
    api.trade_history(INS, 20240929, [], status=500)

    with pytest.raises(DataUnavailable, match="2024-09-29"):
        ticker.history(start="2024-09-29", end="2024-09-30", interval="5m")


def test_the_latest_session_comes_from_the_live_trade_feed(api):
    # the daily list does not hold the running session yet; GetClosingPriceInfo names it
    ticker = _folad(api, [_bar(20240929, 100, count=1)], latest=20240930, latest_count=1)
    api.trade_history(INS, 20240929, [_trade(1, 90000, 100, 10)])
    api.trades(INS, [_trade(1, 91500, 102, 3)])

    frame = ticker.history(start="2024-09-29", end="2024-10-01", interval="15m")

    assert list(frame.index) == [_at("2024-09-29 09:00"), _at("2024-09-30 09:15")]
    assert frame["Close"].iloc[-1] == 102


def test_bars_before_an_ex_date_are_adjusted_and_the_dividend_lands_on_its_first_bar(api):
    ticker = _folad(
        api,
        [_bar(20240929, 110, count=2), _bar(20241001, 60, count=1)],
        adjust=[{"dEven": 20241001, "pClosing": 55, "pClosingNotAdjusted": 110}],
    )
    api.trade_history(INS, 20240929, [_trade(1, 90000, 100, 1), _trade(2, 120000, 110, 1)])
    api.trade_history(INS, 20241001, [_trade(1, 90000, 60, 1)])

    adjusted = ticker.history(start="2024-09-29", end="2024-10-02", interval="1h")
    raw = ticker.history(start="2024-09-29", end="2024-10-02", interval="1h", auto_adjust=False)

    assert list(adjusted["Close"]) == pytest.approx([50.0, 55.0, 60.0])
    assert list(adjusted["Dividends"]) == [0.0, 0.0, 55.0]
    assert list(raw["Close"]) == [100.0, 110.0, 60.0]
    assert list(raw["Adj Close"]) == pytest.approx([50.0, 55.0, 60.0])


def test_actions_from_before_the_window_stay_out_of_it(api):
    # فولاد's 2026-08-03 dividend and 2026-03-30 split landed on the first bar of a September window
    ticker = _folad(
        api,
        [_bar(20240902, 90, count=1), _bar(20240929, 100, count=1)],
        adjust=[{"dEven": 20240901, "pClosing": 80, "pClosingNotAdjusted": 100}],
        shares=[{"dEven": 20240815, "numberOfShareOld": 100, "numberOfShareNew": 200}],
    )
    api.trade_history(INS, 20240929, [_trade(1, 90000, 100, 1)])

    frame = ticker.history(start="2024-09-29", end="2024-09-30", interval="1h")

    assert (frame["Dividends"].sum(), frame["Stock Splits"].sum()) == (0.0, 0.0)
    assert frame["Close"].iloc[0] == 100.0


def test_an_ex_date_just_before_the_window_lands_on_its_first_session(api):
    # 2024-09-28 was halted; the first session at or after the ex-date is inside the window
    ticker = _folad(
        api,
        [_bar(20240925, 110, count=1), _bar(20240929, 60, count=1)],
        adjust=[{"dEven": 20240928, "pClosing": 55, "pClosingNotAdjusted": 110}],
    )
    api.trade_history(INS, 20240929, [_trade(1, 90000, 60, 1), _trade(2, 110000, 61, 1)])

    frame = ticker.history(start="2024-09-29", end="2024-09-30", interval="1h")

    assert list(frame["Dividends"]) == [55.0, 0.0]


@pytest.mark.parametrize(
    "window",
    [{"period": "max"}, {"end": "2024-10-01"}, {"start": "2024-01-01", "end": "2024-06-01"}],
)
def test_an_intraday_window_longer_than_three_months_is_rejected(api, window):
    ticker = _folad(api, [_bar(20240929, 100)])

    with pytest.raises(ValueError, match="3 months"):
        ticker.history(interval="5m", **window)


def test_three_months_is_within_the_cap(api):
    ticker = _folad(api, [_bar(20240929, 100)])

    frame = ticker.history(period="3mo", interval="1h")

    assert frame.empty
    assert frame.index.name == "Datetime"


def test_indices_have_no_intraday_bars(api):
    api.search("شاخص کل", [])
    api.indices(1, [{"insCode": "3209", "lVal30": "شاخص كل"}])

    with pytest.raises(NotImplementedError, match="index"):
        Ticker("شاخص کل").history(period="5d", interval="5m")


def test_tsetmc_and_crypto_hourly_bars_share_one_download(api, monkeypatch):
    # crypto 1h bars are UTC, TSETMC's Tehran; one naive and one aware index cannot be joined
    from yfinance_ir import download
    from yfinance_ir.sources import crypto

    monkeypatch.setattr(
        crypto, "ohlcv", lambda pair, since=None, timeframe="1d": [[1727586000000, 1.0, 2.0, 0.5, 1.5, 9.0]]
    )
    _folad(api, [_bar(20240929, 100, count=1)])
    api.trade_history(INS, 20240929, [_trade(1, 93000, 100, 1)])

    frame = download(
        ["فولاد", "BTC-IRT"],
        start="2024-09-29",
        end="2024-09-30",
        interval="1h",
        progress=False,
        threads=False,
    )

    assert frame[("Close", "فولاد")].dropna().index[0] == _at("2024-09-29 09:00")
    assert frame[("Close", "BTC-IRT")].dropna().index[0] == pd.Timestamp("2024-09-29 05:00", tz="UTC")


def test_real_trades_rebuild_the_sessions_open(api):
    # فولاد, 2024-09-30: TSETMC's daily bar opened at 4,192; the fixture is the first half hour
    rows = load_fixture("tsetmc_trades_folad_20240930.json")["tradeHistory"]
    ticker = _folad(api, [_bar(20240930, 4185, count=len(rows))])
    api.trade_history(INS, 20240930, rows)

    frame = ticker.history(start="2024-09-30", end="2024-10-01", interval="1m")

    assert frame.index[0] == _at("2024-09-30 09:00")
    assert frame["Open"].iloc[0] == 4192.0
    assert frame["Volume"].sum() == sum(row["qTitTran"] for row in rows if not row["canceled"])
    assert frame["Count"].sum() == sum(1 for row in rows if not row["canceled"])
