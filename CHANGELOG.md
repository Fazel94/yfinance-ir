# Changelog

Versions are CalVer, `YYYY.M.MICRO`: the year and month of the release, then a counter
for further releases in that month. The number records the release date. Breaking
changes are named in the entry.

## 2026.9.1 - 2026-09-24

- Fixed: `history()` ignored capital increases that TSETMC's `GetPriceAdjustList` omits.
  فولاد's share count rose 209B to 1,935B in 2020-2026 with one adjust row, so its
  5-year adjusted return read -50% instead of +228%. Every `GetInstrumentShareChange`
  row without an adjust row within ±3 days is now a bonus issue: `Stock Splits =
  new / old` and earlier bars multiplied by `old / new`. Rights issues paid in cash are
  over-adjusted; TSETMC does not distinguish them.
- Changed: `Dividends` and `Stock Splits` land on the first bar at or after the ex-date
  instead of being dropped when the ex-date has no bar.
- Added: `examples/real_returns.py`, فولاد in Rial, TGJU USD and CPI-deflated terms.
- Fixed: the bonus-issue inference above was applied to funds, whose unit count moves
  with every creation and redemption. آوند's adjusted series showed a +520% day and a
  156% CAGR against a raw 10,000 to 30,309 Rial (29%). `kind == "ETF"` instruments now
  take only TSETMC's own adjust rows.
- Added: `examples/cookbook.ipynb`, chapters 1, 2 and 7 of *Python for Finance Cookbook*
  on TSETMC, Nobitex, TGJU and SCI data, with the stylised facts tested, returns restated
  in CPI and dollar terms, idle cash held in آوند or USD, and آوند's yield as the
  risk-free rate.

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
