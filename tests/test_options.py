import pandas as pd
import pytest
from conftest import load_fixture

from yfinance_ir.exceptions import DataUnavailable
from yfinance_ir.ticker import Ticker

AHROM = "17914401175772326"


def _pair(strike, end, *, ua=AHROM, underlying=67650.0, **fields):
    """One ``GetInstrumentOptionMarketWatch`` row: a call and a put on the same strike."""
    row = {"uaInsCode": ua, "strikePrice": strike, "beginDate": "20260701", "endDate": end,
           "contractSize": 1000, "remainedDay": 27, "lval30_UA": "اهرم",
           "pDrCotVal_UA": underlying, "pClosing_UA": 67285.0, "priceYesterday_UA": 66017.0}
    for leg, prefix in (("C", "ض"), ("P", "ط")):
        row.update({
            f"insCode_{leg}": f"{leg}{strike}{end}", f"lVal18AFC_{leg}": f"{prefix}هرم{strike}",
            f"lVal30_{leg}": f"{leg} اهرم-{strike}", f"pDrCotVal_{leg}": 100.0,
            f"pClosing_{leg}": 90.0, f"priceYesterday_{leg}": 80.0, f"pMeDem_{leg}": 99.0,
            f"qTitMeDem_{leg}": 5, f"pMeOf_{leg}": 101.0, f"qTitMeOf_{leg}": 6,
            f"qTotTran5J_{leg}": 10, f"qTotCap_{leg}": 1000.0, f"zTotTran_{leg}": 2,
            f"oP_{leg}": 50, f"yesterdayOP_{leg}": 40, f"notionalValue_{leg}": 0.0,
        })
    row.update(fields)
    return row


def _ahrom(api, rows):
    api.search("اهرم", [{"insCode": AHROM, "lVal18AFC": "اهرم", "lVal30": "اهرم"}])
    api.identity(AHROM, symbol="اهرم", isin="IRT1AHRM0005", market="بازار صندوق های قابل معامله")
    api.option_watch(rows)
    return Ticker("اهرم")


def test_expirations_list_only_this_underlying_in_iso_order(api):
    ticker = _ahrom(api, [
        _pair(20000, "20261021"),
        _pair(26000, "20261021"),
        _pair(20000, "20260923"),
        _pair(5000, "20261111", ua="999"),
    ])

    assert ticker.options == ("2026-09-23", "2026-10-21")


def test_each_pair_becomes_a_call_and_a_put_sorted_by_strike(api):
    ticker = _ahrom(api, [_pair(70000, "20261021", pDrCotVal_C=120.0), _pair(60000, "20261021")])

    chain = ticker.option_chain("2026-10-21")

    assert list(chain.calls["strike"]) == [60000.0, 70000.0]
    assert list(chain.puts["strike"]) == [60000.0, 70000.0]
    call = chain.calls.iloc[1]
    assert call["contractSymbol"] == "ضهرم70000"
    assert call["insCode"] == "C7000020261021"
    assert (call["lastPrice"], call["bid"], call["ask"]) == (120.0, 99.0, 101.0)
    assert (call["bidSize"], call["askSize"]) == (5, 6)
    assert call["change"] == pytest.approx(40.0)  # last 120 vs previous close 80
    assert call["percentChange"] == pytest.approx(50.0)
    assert (call["volume"], call["openInterest"], call["contractSize"]) == (10, 50, 1000)
    assert call["currency"] == "IRR"
    assert chain.puts.iloc[0]["contractSymbol"] == "طهرم60000"
    assert chain.underlying["regularMarketPrice"] == 67650.0


def test_in_the_money_compares_the_strike_with_the_underlyings_last_price(api):
    ticker = _ahrom(api, [_pair(60000, "20261021"), _pair(70000, "20261021")])

    chain = ticker.option_chain()

    assert list(chain.calls["inTheMoney"]) == [True, False]  # underlying last 67,650
    assert list(chain.puts["inTheMoney"]) == [False, True]


def test_the_default_chain_is_the_nearest_expiration(api):
    ticker = _ahrom(api, [_pair(20000, "20261118"), _pair(30000, "20261021")])

    chain = ticker.option_chain()

    assert list(chain.calls["strike"]) == [30000.0]


def test_a_jalali_expiration_selects_the_same_chain(api):
    ticker = _ahrom(api, [_pair(20000, "20261118"), _pair(30000, "20261021")])

    # 1405-07-29 == 2026-10-21
    assert list(ticker.option_chain("1405-07-29").calls["strike"]) == [30000.0]


def test_an_unlisted_expiration_names_the_listed_ones(api):
    ticker = _ahrom(api, [_pair(20000, "20261021")])

    with pytest.raises(ValueError, match="2026-10-21"):
        ticker.option_chain("2026-12-16")


def test_an_underlying_without_options_has_none(api):
    ticker = _ahrom(api, [_pair(5000, "20261111", ua="999")])

    assert ticker.options == ()
    with pytest.raises(DataUnavailable, match="no options"):
        ticker.option_chain()


def test_real_market_watch_rows_parse(api):
    rows = load_fixture("tsetmc_option_watch.json")["instrumentOptMarketWatch"]
    ticker = _ahrom(api, rows)

    expirations = ticker.options
    chain = ticker.option_chain(expirations[-1])

    assert expirations == tuple(sorted(expirations)) and len(expirations) == 3
    assert len(chain.calls) == len(chain.puts) > 0
    assert (chain.calls["strike"] > 0).all()
    assert chain.calls["contractSymbol"].str.startswith("ضهرم").all()
    assert chain.puts["contractSymbol"].str.startswith("طهرم").all()
    assert pd.api.types.is_bool_dtype(chain.calls["inTheMoney"])
    assert chain.underlying["regularMarketPrice"] > 0
