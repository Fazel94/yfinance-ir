# yfinance-ir

[![CI](https://github.com/Fazel94/yfinance-ir/actions/workflows/ci.yml/badge.svg)](https://github.com/Fazel94/yfinance-ir/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.9%20%7C%203.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

`yfinance`-shaped market data for the Iranian markets: TSETMC (equities, ETFs, indices),
Codal (financial statements), TGJU (FX, gold, coins), the Statistical Centre of Iran (CPI)
and, with the `crypto` extra, Iranian crypto exchanges through `ccxt-ir`.

> **Iranian IP required.** `cdn.tsetmc.com` drops foreign IPs.


## Install

```bash
pip install yfinance-ir              # TSETMC + Codal + TGJU + CPI
pip install "yfinance-ir[crypto]"    # adds BTC-IRT / ETH-USDT style pairs
```

## Quickstart

```python
import yfinance_ir as yf

folad = yf.Ticker("فولاد")
folad.history(period="1y")          # adjusted daily OHLCV
folad.info["marketCap"]
folad.income_stmt                   # Codal, wide, newest period first

yf.download(["فولاد", "فملی"], period="6mo")
yf.Ticker("USD").history(period="5y")   # TGJU dollar, Rial
yf.Ticker("شاخص کل").history()          # TEDPIX
yf.Ticker("CPI").history()              # SCI consumer price index, monthly
yf.Ticker("BTC-IRT").history()          # Nobitex, needs the `crypto` extra
```

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
| `history(...)` | TSETMC / TGJU / SCI / crypto | daily OHLCV (monthly for CPI), adjusted by default |
| `info` | TSETMC | yfinance-style keys: `marketCap`, `trailingPE`, `sharesOutstanding`, … |
| `dividends`, `splits`, `actions` | TSETMC adjust + share-change | see docs/conventions.md |
| `orderbook` | TSETMC / exchange | 5 levels, bid/ask price-volume-count |
| `client_types`, `client_type_history()` | TSETMC | individual vs institutional flow |
| `major_holders` | TSETMC | > 1 % shareholders |
| `news` | Codal summaries + TSETMC supervisor messages | |
| `income_stmt`, `balance_sheet`, `quarterly_*` | Codal | wide frame, columns = period end |
| `monthly_activity()` | Codal | monthly production/sales letters |

`Tickers("فولاد فملی")` bundles several tickers. `download([...])` returns the yfinance
`MultiIndex` layout: `group_by="column"` gives `(Price, Ticker)`, `group_by="ticker"` flips it.

## Conventions

| Topic | Rule |
|---|---|
| Prices | TSETMC and TGJU in Rial; `*-IRT` crypto pairs in Toman |
| Columns | `Open High Low Close Volume Dividends "Stock Splits"`, plus TSETMC `Last`, `Value`, `Count`; `auto_adjust=False` adds `Adj Close` |
| Dates | Gregorian `DatetimeIndex`; `start`/`end` accept Gregorian, Jalali (`1403-01-01`), `dEven` ints, `date`/`datetime`; `end` exclusive |
| Adjustment | Multiplicative factors from TSETMC `GetPriceAdjustList`; cash difference becomes `Dividends`, share-count changes become `Stock Splits` |
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

- Daily bars only; `interval` other than `1d` raises `NotImplementedError` (crypto also
  takes `1h`, CPI `1mo`).
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
.venv/bin/python -m pytest                   # 64 offline tests, replayed fixtures
.venv/bin/python -m pytest -m live           # 9 smoke tests, needs an Iranian IP
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
