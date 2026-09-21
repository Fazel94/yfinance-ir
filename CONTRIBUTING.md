# Contributing

## Setup

    python -m venv .venv && .venv/bin/pip install -e ".[dev,crypto]"

## Checks

`ruff check .` and `python -m pytest` must pass. CI runs both on Python 3.9 to 3.13 with
`-W error::DeprecationWarning`, so a new deprecation warning fails the build.

## Tests

Offline tests live in `tests/` and replay `tests/fixtures/` through `responses`; unmapped
requests raise. Add a fixture and a route in `tests/conftest.py` (`Api` class) when you call a
new upstream URL. Tests marked `live` hit the real endpoints and need an Iranian IP:
`python -m pytest -m live`.

To re-record fixtures, run `python tests/capture_fixtures.py` from the repository root with
Iranian egress. It overwrites `tests/fixtures/`.

## Versioning

CalVer, `YYYY.M.MICRO`. Bump `__version__` in `yfinance_ir/__init__.py` and add an entry to
`CHANGELOG.md` in the same commit. Name breaking changes in the entry.
