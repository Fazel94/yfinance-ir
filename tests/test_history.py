import pandas as pd
import pytest

from yfinance_ir.resolver import resolve
from yfinance_ir.ticker import Ticker


def _bar(deven, close, *, first=None, high=None, low=None, volume=1000, count=10):
    return {
        "dEven": deven,
        "priceFirst": first if first is not None else close,
        "priceMax": high if high is not None else close,
        "priceMin": low if low is not None else close,
        "pClosing": close,
        "pDrCotVal": close,
        "qTotTran5J": volume,
        "qTotCap": close * volume,
        "zTotTran": count,
    }


BARS = [
    _bar(20231226, 100),
    _bar(20231227, 110),
    _bar(20240101, 60),  # ex-date: 100 -> 50 adjustment
    _bar(20240102, 65),
]
ADJUST = [{"dEven": 20240101, "pClosing": 55, "pClosingNotAdjusted": 110}]


def _folad(api, *, adjust=ADJUST, shares=(), bars=BARS):
    api.search("فولاد", [{"insCode": "222", "lVal18AFC": "فولاد", "lVal30": "فولاد"}])
    api.equity("222", symbol="فولاد", rows=bars, adjust=adjust, shares=shares)
    return Ticker("فولاد")


def test_adjusted_closes_scale_only_the_bars_before_the_ex_date(api):
    frame = _folad(api).history(period="max")

    assert list(frame.columns) == ["Open", "High", "Low", "Close", "Volume", "Dividends",
                                   "Stock Splits", "Last", "Value", "Count"]
    # ratio = 55/110 = 0.5 applies to every bar strictly before 2024-01-01
    assert frame.loc["2023-12-26", "Close"] == pytest.approx(50.0)
    assert frame.loc["2023-12-27", "Close"] == pytest.approx(55.0)
    assert frame.loc["2024-01-01", "Close"] == pytest.approx(60.0)
    assert frame.loc["2024-01-02", "Close"] == pytest.approx(65.0)
    assert frame.loc["2023-12-26", "Open"] == pytest.approx(50.0)


def test_auto_adjust_false_keeps_raw_prices_and_adds_adj_close(api):
    frame = _folad(api).history(period="max", auto_adjust=False)

    assert frame.loc["2023-12-26", "Close"] == pytest.approx(100.0)
    assert frame.loc["2023-12-26", "Adj Close"] == pytest.approx(50.0)
    assert frame.loc["2024-01-02", "Adj Close"] == pytest.approx(65.0)
    assert list(frame.columns).index("Adj Close") == 4


def test_factors_compound_across_several_events(api):
    ticker = _folad(
        api,
        adjust=[
            {"dEven": 20231227, "pClosing": 80, "pClosingNotAdjusted": 100},
            {"dEven": 20240101, "pClosing": 55, "pClosingNotAdjusted": 110},
        ],
    )

    frame = ticker.history(period="max")

    # the oldest bar sits before both events -> 0.8 * 0.5
    assert frame.loc["2023-12-26", "Close"] == pytest.approx(40.0)
    assert frame.loc["2023-12-27", "Close"] == pytest.approx(55.0)


def test_cash_adjustment_is_a_dividend_and_a_share_change_is_a_split(api):
    ticker = _folad(api, shares=[{"dEven": 20240101, "numberOfShareOld": 100, "numberOfShareNew": 200}])

    assert ticker.dividends.empty
    assert ticker.splits.loc[pd.Timestamp("2024-01-01")] == pytest.approx(2.0)

    cash = _folad(api)
    assert cash.dividends.loc[pd.Timestamp("2024-01-01")] == pytest.approx(55.0)
    assert cash.splits.empty


def test_actions_land_on_the_bar_of_their_ex_date(api):
    frame = _folad(api).history(period="max")

    assert frame.loc["2024-01-01", "Dividends"] == pytest.approx(55.0)
    assert frame.loc["2023-12-27", "Dividends"] == 0.0


def test_start_is_inclusive_and_end_is_exclusive(api):
    frame = _folad(api).history(start="2023-12-27", end="2024-01-02")

    assert [str(ts.date()) for ts in frame.index] == ["2023-12-27", "2024-01-01"]


def test_jalali_dates_can_be_used_as_bounds_and_as_a_column(api):
    frame = _folad(api).history(start="1402-10-06", jalali=True)  # 1402-10-06 == 2023-12-27

    assert [str(ts.date()) for ts in frame.index] == ["2023-12-27", "2024-01-01", "2024-01-02"]
    assert frame["JDate"].iloc[0] == "1402-10-06"


def test_non_trading_calendar_rows_are_dropped(api):
    bars = BARS + [_bar(20240103, 65, volume=0, count=0)]

    frame = _folad(api, bars=bars).history(period="max")

    assert "2024-01-03" not in [str(ts.date()) for ts in frame.index]


def test_alternate_listings_are_merged_with_the_primary_winning(api):
    api.search(
        "فولاد",
        [
            {"insCode": "111", "lVal18AFC": "فولاد", "lVal30": "old"},
            {"insCode": "222", "lVal18AFC": "فولاد", "lVal30": "new"},
        ],
    )
    api.quote("111", dEven=20200101)
    api.quote("222", dEven=20260920)
    api.equity("222", symbol="فولاد", rows=BARS, adjust=[])
    api.daily("111", [_bar(20231220, 10), _bar(20231226, 999)])

    frame = Ticker("فولاد").history(period="max")

    assert frame.loc["2023-12-20", "Close"] == pytest.approx(10.0)  # only the old listing has it
    assert frame.loc["2023-12-26", "Close"] == pytest.approx(100.0)  # primary wins the overlap


def test_index_history_uses_close_for_open_and_has_no_volume(api, session):
    api.search("شاخص کل", [])
    api.indices(1, [{"insCode": "3209", "lVal30": "شاخص كل"}])
    api.index_history(
        "3209",
        [{"dEven": 20240101, "xNivInuClMresIbs": 2_100_000.0,
          "xNivInuPhMresIbs": 2_150_000.0, "xNivInuPbMresIbs": 2_050_000.0}],
    )

    instrument = resolve(session, "شاخص کل")
    frame = Ticker("شاخص کل").history(period="max")

    assert instrument.kind == "INDEX"
    assert frame.loc["2024-01-01", "Open"] == frame.loc["2024-01-01", "Close"] == 2_100_000.0
    assert frame.loc["2024-01-01", "High"] == 2_150_000.0
    assert pd.isna(frame.loc["2024-01-01", "Volume"])


def test_tgju_rows_map_to_ohlc_in_the_published_column_order(api):
    api.tgju_summary(
        "price_dollar_rl",
        [["2,266,000", "2,265,600", "2,303,200", "2,302,750", "", "", "2026/09/20", "1405/06/29"]],
    )

    frame = Ticker("USD").history(period="max")

    row = frame.loc["2026-09-20"]
    assert (row["Open"], row["Low"], row["High"], row["Close"]) == (2266000, 2265600, 2303200, 2302750)


def test_tgju_falls_back_to_the_profile_chart_when_the_api_is_empty(api):
    api.tgju_summary("price_dollar_rl", [])
    api.tgju_profile(
        "price_dollar_rl",
        "<html><script>chartData: [[1600000000000, 250000],[1600086400000, 260000]]</script></html>",
    )

    frame = Ticker("USD").history(period="max")

    assert len(frame) == 2
    assert frame["Open"].iloc[0] == frame["High"].iloc[0] == frame["Close"].iloc[0] == 250000


def test_unsupported_interval_is_rejected(api):
    with pytest.raises(NotImplementedError):
        _folad(api).history(interval="1h")
