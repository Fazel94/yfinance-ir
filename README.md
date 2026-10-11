# yfinance-ir

[![CI](https://github.com/Fazel94/yfinance-ir/actions/workflows/ci.yml/badge.svg)](https://github.com/Fazel94/yfinance-ir/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

[فارسی](README.fa.md)

`yfinance`-shaped market data for the Iranian markets: TSETMC (equities, ETFs, indices),
Codal (financial statements), TGJU (FX, gold, coins), the Statistical Centre of Iran (CPI)
and, with the `crypto` extra, Iranian crypto exchanges through `ccxt-ir`.

> **Iranian IP required.** `cdn.tsetmc.com` drops foreign IPs.

[![Since Nowruz 1405: which assets beat inflation and which beat the dollar](examples/scoreboard.png)](examples/scoreboard.ipynb)

One `history()` call per bar: TSETMC indices, stocks and ETFs, TGJU's dollar, euro, gold
and coin, Nobitex bitcoin, measured against the SCI CPI and the free-market dollar.
[`examples/scoreboard.ipynb`](examples/scoreboard.ipynb) draws it, the same race as a
path since Nowruz and over five years, and a seven-window heatmap of real and dollar
returns. Charts are in Persian; install from `main` for its two text-shaping extras:
`pip install "yfinance-ir[crypto,notebook] @ git+https://github.com/Fazel94/yfinance-ir.git"`.

Monthly update of this chart: X [@_fazel94](https://x.com/_fazel94)


## Install

```bash
pip install "yfinance-ir @ git+https://github.com/Fazel94/yfinance-ir.git@v2026.9.2"          # TSETMC + Codal + TGJU + CPI
pip install "yfinance-ir[crypto] @ git+https://github.com/Fazel94/yfinance-ir.git@v2026.9.2"  # adds BTC-IRT / ETH-USDT style pairs
```

Not on PyPI yet: install from a release tag. Each [GitHub Release](https://github.com/Fazel94/yfinance-ir/releases) also carries the wheel and sdist.

## Quickstart

```python
import yfinance_ir as yf

folad = yf.Ticker("فولاد")
folad.history(period="1y")          # adjusted daily OHLCV
folad.history(period="5d", interval="5m")   # intraday bars rebuilt from TSETMC trades
folad.info["marketCap"]
folad.income_stmt                   # Codal, wide, newest period first
folad.cashflow                      # Codal cash-flow statement
yf.Ticker("اهرم").option_chain()    # nearest expiration: calls, puts, underlying

yf.download(["فولاد", "فملی"], period="6mo")
yf.Ticker("USD").history(period="5y")   # TGJU dollar, Rial
yf.Ticker("شاخص کل").history()          # TEDPIX
yf.Ticker("CPI").history()              # SCI consumer price index, monthly
yf.Ticker("BTC-IRT").history()          # Nobitex, needs the `crypto` extra
```

### Example: فولاد in Rial, USD and real terms

[`examples/real_returns.py`](examples/real_returns.py) prices فولاد in TGJU dollars and
deflates it by the SCI CPI. Both series are forward-filled onto the stock's trading days.

```python
import pandas as pd

folad = yf.Ticker("فولاد").history(period="5y")["Close"]
usd = yf.Ticker("USD").history(period="5y")["Close"].reindex(folad.index, method="ffill")
cpi = yf.Ticker("CPI").history(period="5y")["Close"].reindex(folad.index, method="ffill")

frame = pd.DataFrame({"Rial": folad, "USD": folad / usd, "Real": folad / cpi * cpi.iloc[-1]})
print(frame.iloc[-1] / frame.iloc[0] - 1)
```

Output on 2026-09-21:

```
فولاد 2021-09-25 -> 2026-09-21 (5.0y)
        total annualised
Rial  +228.1%     +26.9%
USD    -60.8%     -17.1%
Real   -52.0%     -13.7%
```

[examples/cookbook.ipynb](examples/cookbook.ipynb) runs the recipes of chapters 1, 2 and 7
of *Python for Finance Cookbook* (returns, CPI deflation, outliers, stylised facts,
SMA/Bollinger/RSI backtests with backtrader, 1/n portfolio, Monte Carlo efficient frontier)
on TSETMC stocks and Nobitex crypto pairs. Install its dependencies with
`pip install "yfinance-ir[crypto,notebook] @ git+https://github.com/Fazel94/yfinance-ir.git@v2026.9.2"`.

## Symbols

| You pass | Resolves to | Example |
|---|---|---|
| Persian symbol | TSETMC instrument | `Ticker("فولاد")`, `Ticker("اهرم")` |
| Persian index name | TSETMC index | `Ticker("شاخص کل")` |
| InsCode (10–20 digits) | TSETMC instrument | `Ticker("46348559193224090")` |
| TGJU alias or slug | FX / gold / coin | `Ticker("USD")`, `Ticker("geram18")` |
| `CPI`, `CPI_URBAN`, `CPI_RURAL` | SCI price index | `Ticker("CPI")` |
| `BASE-IRT` / `BASE-USDT` | crypto pair | `Ticker("BTC-IRT")` |
| ISIN | cache lookup only, see below | `Ticker("IRO1FOLD0009")` |

Persian and Arabic spellings are unified (`ی`/`ي`, `ک`/`ك`, ZWNJ). TGJU aliases and the
per-source rules are in [docs/data-sources.md](docs/data-sources.md). Resolutions are cached
in `~/.cache/yfinance_ir/symbols.sqlite`; `yf.cache.clear()` drops them,
`yf.set_config(cache_dir=...)` moves them.

## Ticker API

| Member | Source | Notes |
|---|---|---|
| `history(...)` | TSETMC / TGJU / SCI / crypto | daily OHLCV (monthly for CPI), adjusted by default; TSETMC also `1m`–`90m` and `1h` bars rebuilt from trades |
| `info` | TSETMC | yfinance-style keys: `marketCap`, `trailingPE`, `sharesOutstanding`, … |
| `dividends`, `splits`, `actions` | TSETMC adjust + share-change | see docs/conventions.md |
| `orderbook` | TSETMC / exchange | 5 levels, bid/ask price-volume-count |
| `client_types`, `client_type_history()` | TSETMC | individual vs institutional flow |
| `major_holders` | TSETMC | > 1 % shareholders |
| `news` | Codal summaries + TSETMC supervisor messages | |
| `income_stmt`, `balance_sheet`, `cashflow`, `quarterly_*` | Codal | wide frame, columns = period end |
| `options`, `option_chain(date)` | TSETMC option market watch | expirations; calls and puts with bid, ask, last, volume, open interest |
| `monthly_activity()` | Codal | monthly production/sales letters |

`Tickers("فولاد فملی")` bundles several tickers. `download([...])` returns the yfinance
`MultiIndex` layout: `group_by="column"` gives `(Price, Ticker)`, `group_by="ticker"` flips it.

## Compared with other packages

| | yfinance-ir | [pytse-client](https://github.com/Glyphack/pytse-client) | [finpy-tse](https://github.com/ARahimiQuant/finpy-tse) | [tehran-stocks](https://github.com/ghodsizadeh/tehran-stocks) |
|---|---|---|---|---|
| Sources | TSETMC, Codal, TGJU, SCI CPI, Nobitex (`crypto` extra) | TSETMC | TSETMC, free-market dollar | TSETMC |
| API shape | yfinance: `Ticker(...).history()`, `download([...])` | `Ticker(...).history` frame, `download(symbols=...)` | `Get_*_History()` functions | SQLAlchemy models + CLI |
| Adjusted daily history | dividends and capital increases | `adjust=True` | `adjust_price=True` | dividend and share tables, no adjusted series documented |
| Intraday bars | `1m`–`90m`, `1h`, rebuilt from trades | `30s`–`1h`, aggregated from trade details (`get_trade_details(..., timeframe=)`) | trade and order-book history, no bars | — |
| Order book, client types | yes | yes | yes | — |
| Codal statements | income, balance sheet, cash flow, monthly activity | — | — | — |
| Option chains | yes | — | — | — |
| FX, gold, coin | TGJU | — | USD only (`Get_USD_RIAL`) | — |
| CPI | SCI, monthly | — | — | — |
| Index history | any TSETMC index by name | `FinancialIndex(...).history` | `Get_CWI_History`, `Get_EWI_History`, sector indices | — |
| Jalali dates | input and output | `include_jdate=True` | `jalali_date=True` | output |
| Licence | MIT | GPL-3.0 | BSD-3-Clause | MIT |
| Last commit | 2026-10 | 2025-03 | 2024-04 | 2023-10 |
| PyPI | not yet, install from a release tag | yes | yes | yes |

Checked against each package's README on 2026-10-11; "—" means the README does not document it.
Corrections welcome as issues.

## Conventions

| Topic | Rule |
|---|---|
| Prices | TSETMC and TGJU in Rial; `*-IRT` crypto pairs in Toman |
| Columns | `Open High Low Close Volume Dividends "Stock Splits"`, plus TSETMC `Last`, `Value`, `Count`; `auto_adjust=False` adds `Adj Close` |
| Dates | Gregorian `DatetimeIndex`; `start`/`end` accept Gregorian, Jalali (`1403-01-01`), `dEven` ints, `date`/`datetime`; `end` exclusive; intraday bars carry a tz-aware `Datetime` index, `Asia/Tehran` for TSETMC and UTC for crypto |
| Adjustment | Dividend gaps from TSETMC `GetPriceAdjustList`; share-count changes it omits are bonus issues (`old / new`); markers land on the next bar |
| Non-trading rows | Zero-volume calendar rows while a symbol is suspended are dropped |
| Errors | `SymbolNotFound`, `BlockedError`, `RateLimitError`, `DataUnavailable`, all subclasses of `YFIRError` |

Full definitions: [docs/conventions.md](docs/conventions.md).

## Configuration

```python
yf.set_config(
    min_interval=0.1,      # seconds between requests to the same host
    timeout=20.0,          # per-request timeout
    threads=4,             # download() workers
    cache_dir=None,        # default: $XDG_CACHE_HOME/yfinance_ir
    crypto_exchange="nobitex",
    trust_env=True,        # honour HTTP(S)_PROXY
)
```

## Limitations

- Intraday bars exist for TSETMC instruments other than indices, span at most 3 months per
  call and cost one request per trading day. Some of TSETMC's backends answer the trade feed
  with HTTP 500 or an empty list; a failed request reconnects to reach another backend, and
  a day still empty after 12 passes (about 3 minutes, long pauses logged at WARNING) raises
  `DataUnavailable`. Other sources: TGJU is daily, crypto `1d`/`1h`, CPI monthly.
- Option chains have no implied volatility or last-trade date; TSETMC publishes neither.
- CPI downloads from `amar.org.ir` run with `verify=False` because the server omits its
  intermediate certificate.
- ISIN lookup only hits the local cache; resolve by symbol or InsCode first.
- Index history has no open or volume.
- `ccxt-ir` 4.19.0's `fetch_ohlcv` and `fetch_order_book` are broken; Nobitex is served
  through its public REST API instead, other exchanges re-raise the ccxt error.

Reasons and endpoint details: [docs/data-sources.md](docs/data-sources.md).

## Development

```bash
python -m venv .venv && .venv/bin/pip install -e ".[dev,crypto]"
.venv/bin/python -m ruff check .
.venv/bin/python -m pytest                   # 95 offline tests, replayed fixtures
.venv/bin/python -m pytest -m live           # 12 smoke tests, needs an Iranian IP
.venv/bin/python tests/capture_fixtures.py   # re-record tests/fixtures/
```

Offline tests run through `responses` against the exact URLs the package calls, so a wrong
path in `yfinance_ir/sources/` fails a test instead of hitting the network.

Versions are CalVer, `YYYY.M.MICRO`. [CHANGELOG.md](CHANGELOG.md) names breaking changes;
the number does not encode them. See [CONTRIBUTING.md](CONTRIBUTING.md).

> **Not affiliated** with yfinance, Yahoo, TSETMC, Codal, TGJU or the Statistical Centre of
> Iran. The package reads their public endpoints and copies the `yfinance` API shape. No
> accuracy guarantee, not investment advice; each source's terms of use are your
> responsibility.

## License

MIT, Copyright (c) 2026 Kiyarash Fazeli. See [LICENSE](LICENSE).
