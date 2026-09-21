import pytest

from yfinance_ir import _cache
from yfinance_ir.exceptions import SymbolNotFound
from yfinance_ir.resolver import normalize, resolve


def test_normalize_unifies_arabic_letters_and_zwnj():
    assert normalize("فولاد\u200cمباركه") == normalize("فولادمبارکه")
    assert normalize("  كيان ") == "کیان"
    assert normalize("دارایی\u200cها", strip_zwnj=False) == "دارایی\u200cها"


def test_symbol_resolves_and_picks_the_most_recently_traded_listing(api, session):
    api.search(
        "فولاد",
        [
            {"insCode": "111", "lVal18AFC": "فولاد", "lVal30": "قدیمی"},
            {"insCode": "222", "lVal18AFC": "فولاد", "lVal30": "فعال"},
            {"insCode": "333", "lVal18AFC": "فولادخوز", "lVal30": "دیگر"},
        ],
    )
    api.quote("111", dEven=20200101)
    api.quote("222", dEven=20260920)
    api.identity("222", symbol="فولاد", name="فولاد مبارکه اصفهان")

    instrument = resolve(session, "فولاد")

    assert instrument.ins_code == "222"
    assert instrument.alt_ins_codes == ("111",)
    assert instrument.kind == "EQUITY"
    assert instrument.isin == "IRO1FOLD0009"


def test_arabic_spelling_hits_the_same_cache_entry(api, session):
    api.search("فملی", [{"insCode": "222", "lVal18AFC": "فملي", "lVal30": "x"}])
    api.identity("222", symbol="فملی")

    first = resolve(session, "فملی")  # Persian ی
    second = resolve(session, "فملي")  # Arabic ي

    assert (first.ins_code, second.ins_code) == ("222", "222")
    assert len(api.mock.calls) == 2  # search + identity; the second call is a cache hit


def test_etf_is_classified_from_its_isin(api, session):
    api.search("اهرم", [{"insCode": "17914401175772326", "lVal18AFC": "اهرم", "lVal30": "اهرم"}])
    api.identity("17914401175772326", symbol="اهرم", isin="IRT1AHRM0001", market="صندوق قابل معامله")

    assert resolve(session, "اهرم").kind == "ETF"


def test_index_name_falls_through_to_the_index_list(api, session):
    api.search("شاخص کل", [])
    api.indices(1, [{"insCode": "32097828799138957", "lVal30": "شاخص كل"}])

    instrument = resolve(session, "شاخص کل")

    assert instrument.kind == "INDEX"
    assert instrument.ins_code == "32097828799138957"


def test_tgju_alias_and_crypto_pair_need_no_network(session):
    # no `api` fixture here: any HTTP call would be a real connection attempt
    assert resolve(session, "USD").source == "tgju"
    assert resolve(session, "USD").ins_code == "price_dollar_rl"
    assert resolve(session, "BTC-IRT").kind == "CRYPTO"


def test_ins_code_resolves_directly_and_caches_the_symbol_too(api, session):
    api.identity("46348559193224090", symbol="فولاد")

    resolve(session, "46348559193224090")

    assert _cache.get_cache().get("فولاد")["ins_code"] == "46348559193224090"


def test_isin_resolves_only_via_the_cache(api, session):
    with pytest.raises(SymbolNotFound, match="local cache"):
        resolve(session, "IRO1FOLD0009")

    api.identity("46348559193224090", symbol="فولاد", isin="IRO1FOLD0009")
    resolve(session, "46348559193224090")

    assert resolve(session, "IRO1FOLD0009").ins_code == "46348559193224090"


def test_unknown_symbol_raises(api, session):
    api.search("قققق", [{"insCode": "9", "lVal18AFC": "قق", "lVal30": "x"}])
    api.indices(1, [])
    api.indices(2, [])

    with pytest.raises(SymbolNotFound):
        resolve(session, "قققق")
