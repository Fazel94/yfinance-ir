# Changelog

Versions are CalVer, `YYYY.M.MICRO`: the year and month of the release, then a counter
for further releases in that month. The number records the release date. Breaking
changes are named in the entry.

## Unreleased

## 2026.9.0 - 2026-09-21

First release.

- `Ticker` over TSETMC equities, ETFs and indices: `history`, `info`, `dividends`,
  `splits`, `actions`, `orderbook`, `client_types`, `client_type_history`,
  `major_holders`, `news`.
- Codal fundamentals: `income_stmt`, `balance_sheet`, the `quarterly_*` variants and
  `monthly_activity()`.
- TGJU FX, gold and coin series. Statistical Centre of Iran CPI (`CPI`, `CPI_URBAN`,
  `CPI_RURAL`) with `MoM` and `YoY` columns.
- Iranian crypto pairs (`BTC-IRT`, `ETH-USDT`) through the `crypto` extra.
- `Tickers(...)` bundles and `download([...])` with the yfinance `MultiIndex` layout.
- Symbol resolution (Persian and Arabic spellings unified, InsCode, TGJU slug, ISIN from
  cache) persisted in `<cache_dir>/symbols.sqlite`.
- Jalali date parsing, TSETMC adjustment factors, and the typed exceptions
  `SymbolNotFound`, `BlockedError`, `RateLimitError`, `DataUnavailable`.
