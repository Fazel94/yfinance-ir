# TODO

Options for continuing after 2026.9.1, which shipped as a GitHub release only. None is started. Let open issues set the order; with none, start with cash-flow statements, the smallest.

## Publish to PyPI

Deferred at 2026.9.1. `https://pypi.org/pypi/yfinance-ir/json` returned 404 on 2026-09-24, so the name was free then; nothing reserves it until the first upload.

- [ ] Pick the upload path.
  - Trusted Publishing: add `.github/workflows/release.yml`, triggered by `release: types: [published]`. A build job runs `python -m build` and `twine check dist/*` and stores `dist/` as an artifact; a publish job with `environment: pypi` and `permissions: id-token: write` downloads it and runs `pypa/gh-action-pypi-publish@release/v1`. One-time setup: a pending publisher at <https://pypi.org/manage/account/publishing/> with project `yfinance-ir`, owner `Fazel94`, repository `yfinance-ir`, workflow `release.yml`, environment `pypi`, plus required reviewers on the `pypi` environment. No token is stored anywhere.
  - Manual: `python -m build && twine upload dist/*` with a PyPI API token, by hand for every release.
- [ ] Add a PyPI version badge to the README.
- [ ] Switch the README install lines back to `pip install yfinance-ir`, `pip install "yfinance-ir[crypto]"` and `pip install "yfinance-ir[crypto,notebook]"`, and tick the PyPI line in `PUBLISH_CHECKLIST.md`.

## Features

Ordered by size.

- [ ] **Cash-flow statements**: `Ticker.cashflow` and `Ticker.quarterly_cashflow`. Small.
  - yfinance has both; `Ticker` stops at `income_stmt`, `balance_sheet` and their `quarterly_*` variants.
  - Reuse `fundamentals.statements()` with a new `codal.SHEET_CASHFLOW` beside `SHEET_BALANCE = 0` and `SHEET_INCOME = 1` in `yfinance_ir/sources/codal.py`. Codal's cash-flow `SheetId` is not known yet; read it off a live filing first.
  - Codal answered on 2026-09-24 from a connection that TSETMC dropped, so its fixtures can be captured without Iranian egress.
- [ ] **Options chains**: `Ticker.options` (expiry dates) and `Ticker.option_chain(date)` (calls and puts). Medium.
  - Needs a TSETMC endpoint that lists an underlying's options (not identified yet), a parser, and fixtures.
  - `cdn.tsetmc.com` drops foreign IPs, so capturing fixtures needs Iranian egress.
- [ ] **Intraday bars**: TSETMC `interval` below `1d`. Large.
  - `history()` raises `NotImplementedError` for any TSETMC interval but `1d` (`_ALLOWED_INTERVALS` in `yfinance_ir/history.py`); it is the first item under README › Limitations.
  - Needs TSETMC's per-day trade feed (not identified yet), trades aggregated into OHLCV bars, one request per trading day under `min_interval`, and fixtures captured from an Iranian IP.
