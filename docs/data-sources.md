# Data sources

One section per upstream. Endpoint paths are the ones the package calls; see
`yfinance_ir/sources/` for the code.

## TSETMC

- Instruments: equities, ETFs, indices. Resolved by Persian symbol, index name or InsCode.
- Daily only. TSETMC's intraday feeds are not wired up; `interval` other than `1d`
  raises `NotImplementedError` (crypto also accepts `1h`, CPI `1mo`).
- Index history has no open or volume. `Index/GetIndexB2History` publishes close,
  high and low only; `Open` mirrors `Close` and `Volume` is `NaN`.
- Today's `client_types` has no values. The live endpoint returns volumes and counts
  only; use `client_type_history()` (legacy feed) for the value columns.
- ISIN lookup is cache-only. TSETMC's search endpoint accepts Persian text only. It
  returns nothing for `IRO1FOLD0009` or `FOLD`, its results carry `cIsin: null`, and the
  official ISIN-keyed `webgw.tse.ir` gateway is WAF-blocked. So an ISIN resolves only
  after that instrument has been resolved by symbol or InsCode at least once.

## Codal

- Financial statements and monthly activity letters.
- Parsing is grid-based. Line items come back as Persian labels exactly as
  filed; a filing whose sheet layout differs is logged at WARNING and skipped.

## TGJU

- FX, gold and coin series in Rial. Aliases: `USD EUR AED GBP TRY CNY CAD AUD GOLD18
  GOLD24 MESGHAL ONS COIN COIN_HALF COIN_QUARTER COIN_GRAM`; any raw TGJU slug also works.

## Statistical Centre of Iran (CPI)

```python
cpi = yf.Ticker("CPI")                      # whole country; CPI_URBAN / CPI_RURAL too
cpi.history(period="5y")[["Close", "MoM", "YoY"]]
cpi.info["annualInflation"]                 # نرخ تورم نقطه‌به‌نقطه of the latest month
```

The Statistical Centre of Iran publishes one workbook per series on
<https://amar.org.ir/prices>, re-stamped on every monthly release, and the download is
cached for a day under `<cache_dir>/sci/`. `Close` is the index level on the published
base year (`info["baseYear"]`, currently 1400 = 100), indexed at the first day of each
Jalali month; `MoM` and `YoY` are percent changes computed from that level. The Central
Bank's inflation pages sit behind a JavaScript challenge and `dataservices.imf.org` is
unreachable from Iranian networks, so neither is usable as a source.

The workbook requests run with `verify=False`. `amar.org.ir` serves its certificate without
the intermediate, so every client fails with `unable to get local issuer certificate`;
those two requests skip verification. The payload is public statistics. CPI is also
released with a lag of a few weeks, and a revision silently replaces the previous
workbook; `yf.cache.clear()` drops the downloaded copies if you need one sooner than
the one-day TTL.

## Crypto (`ccxt-ir`)

- Pairs `BASE-IRT` / `BASE-USDT`; `*-IRT` quoted in Toman (see docs/conventions.md, Prices).
- `ccxt-ir` 4.19.0 is partly broken. `fetch_ohlcv` raises
  `NameError: name 'Date' is not defined` on *every* exchange and `fetch_order_book`
  raises a `TypeError`. Both are routed around using Nobitex's public REST API
  (`/market/udf/history`, `/v3/orderbook/{PAIR}`) discovered from ccxt's own
  `urls["api"]["public"]`. Other exchanges re-raise the ccxt error.
