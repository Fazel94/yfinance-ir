"""Dev-only: record live upstream responses into ``tests/fixtures/``.

Run from the repo root with Iranian egress:

    python tests/capture_fixtures.py

Offline unit tests replay these bodies through ``responses``; nothing in the package
imports this module.
"""

import datetime as _dt
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from yfinance_ir import _http, intraday, set_config  # noqa: E402
from yfinance_ir.sources import codal, tgju, tsetmc  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

FOLAD = "46348559193224090"
AHROM = "17914401175772326"
TEDPIX = tsetmc.TEDPIX_INS_CODE


def _write(name: str, payload) -> None:
    os.makedirs(FIXTURES, exist_ok=True)
    path = os.path.join(FIXTURES, name)
    if isinstance(payload, (dict, list)):
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
    else:
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(payload)
    print(f"wrote {name} ({os.path.getsize(path)} bytes)")


def main() -> None:
    set_config(trust_env=False)
    session = _http.new_session()

    _write("tsetmc_search_folad.json", {"instrumentSearch": tsetmc.search(session, "فولاد")})
    _write("tsetmc_identity_folad.json", {"instrumentIdentity": tsetmc.identity(session, FOLAD)})
    _write("tsetmc_info_folad.json", {"instrumentInfo": tsetmc.info(session, FOLAD)})
    _write(
        "tsetmc_closingprice_info_folad.json",
        {"closingPriceInfo": tsetmc.closing_price_info(session, FOLAD)},
    )
    _write(
        "tsetmc_daily_folad.json",
        {"closingPriceDaily": tsetmc.closing_price_daily_list(session, FOLAD)[:400]},
    )
    _write("tsetmc_adjust_folad.json", {"priceAdjust": tsetmc.price_adjust_list(session, FOLAD)})
    _write(
        "tsetmc_sharechange_folad.json",
        {"instrumentShareChange": tsetmc.share_change(session, FOLAD)},
    )
    _write("tsetmc_bestlimits_folad.json", {"bestLimits": tsetmc.best_limits(session, FOLAD)})
    _write("tsetmc_clienttype_folad.json", {"clientType": tsetmc.client_type(session, FOLAD)})
    _write("tsetmc_clienttype_history_folad.txt", tsetmc.client_type_history_txt(session, FOLAD)[:4000])
    _write("tsetmc_identity_ahrom.json", {"instrumentIdentity": tsetmc.identity(session, AHROM)})
    _write("tsetmc_etf_ahrom.json", {"etf": tsetmc.etf(session, AHROM)})
    _write("tsetmc_indices_flow1.json", {"indexB1": tsetmc.indices_all(session, 1)})
    _write(
        "tsetmc_index_history_tedpix.json",
        {"indexB2": tsetmc.index_history(session, TEDPIX)[-500:]},
    )
    last_deven = int(tsetmc.closing_price_info(session, FOLAD).get("dEven") or 0)
    _write(
        "tsetmc_shareholders_folad.json",
        {"shareShareholder": tsetmc.shareholders(session, FOLAD, last_deven)},
    )
    _write("tsetmc_codal_prepared_folad.json", {"preparedData": tsetmc.codal_prepared(session, FOLAD, 5)})
    watch = tsetmc.option_market_watch(session, 0)
    _write(
        "tsetmc_option_watch.json",
        {
            "instrumentOptMarketWatch": [r for r in watch if r["uaInsCode"] == AHROM]
            + [r for r in watch if r["uaInsCode"] != AHROM][:6]
        },
    )
    trades = intraday.fetch_trades(session, FOLAD, _dt.date(2024, 9, 30))
    _write(
        "tsetmc_trades_folad_20240930.json",
        {"tradeHistory": [row for row in trades if row["hEven"] < 93000]},  # first half hour
    )

    _write(
        "tgju_summary_usd.json",
        _raw_json(session, f"{tgju.API}/indicator/summary-table-data/price_dollar_rl", length=400),
    )

    letters = codal.letters(
        session,
        "فولاد",
        category=codal.CATEGORY_FINANCIAL,
        letter_type=codal.LETTER_INTERIM_FS,
        from_jdate="1403/01/01",
        to_jdate="1405/12/29",
    )
    _write("codal_letters_folad.json", {"Total": len(letters), "Page": 1, "Letters": letters[:5]})
    _write(
        "codal_income_folad.json",
        codal.datasource(session, letters[0]["Url"], codal.SHEET_INCOME),
    )
    _write(
        "codal_cashflow_folad.json",
        codal.datasource(session, letters[0]["Url"], codal.SHEET_CASHFLOW),
    )


def _raw_json(session, url: str, length: int) -> dict:
    params = {"lang": "fa", "order_dir": "asc", "draw": 1, "start": 0, "length": length}
    return _http.get(session, url, params=params).json()


if __name__ == "__main__":
    main()
