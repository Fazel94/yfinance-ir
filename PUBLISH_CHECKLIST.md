# Publish-to-GitHub checklist

Audit date 2026-09-21. Verified on this tree: 64 tests pass on Python 3.10.12, 3.11.12
and 3.12.2 (9 live tests deselected) with `-W error::DeprecationWarning`, `ruff check .`
is clean, and `python -m build` plus `twine check` pass for the sdist and the wheel,
which installs and imports in a fresh 3.10 venv.

`[x]` is done, `[ ]` is open.

## Done in this pass

- [x] Copyright holder set to Kiyarash Fazeli in `LICENSE` and in `pyproject.toml`
      (`authors`, with caci96@gmail.com).
- [x] Non-affiliation and no-investment-advice notice added to `README.md` and to the
      `yfinance_ir` package docstring.
- [x] CalVer. `__version__ = "2026.9.0"` in `yfinance_ir/__init__.py` is the single
      source; `pyproject.toml` reads it through `[tool.setuptools.dynamic]`.
      `CHANGELOG.md` and the README state the `YYYY.M.MICRO` scheme.
- [x] `[project.urls]` points at `github.com/Fazel94/yfinance-ir` (Homepage, Repository,
      Issues, Changelog).
- [x] License metadata modernised to PEP 639: `license = "MIT"` plus
      `license-files = ["LICENSE"]`, and the `License ::` classifier dropped. Needs
      `setuptools>=77`, which `build-system.requires` now pins. The wheel carries
      `dist-info/licenses/LICENSE`.
- [x] `yfinance_ir/py.typed` added and shipped via `[tool.setuptools.package-data]`, so
      downstream mypy and pyright see the annotations.
- [x] Classifiers for 3.9 through 3.13 plus `Operating System :: OS Independent`.
- [x] `ruff` added to the `dev` extra; `numpy` floored at 1.21.
- [x] `logging.NullHandler()` attached to the `yfinance_ir` logger at import.
- [x] `download()` progress counter now increments under a lock, and the bar is written
      only when `sys.stdout.isatty()`. Verified: a threaded all-failing download with
      `progress=True` under redirected stdout writes 0 bytes.
- [x] `datetime.utcfromtimestamp()` in `yfinance_ir/sources/tgju.py:133` replaced with
      `datetime.fromtimestamp(..., timezone.utc)`. It was the only DeprecationWarning on
      3.12.
- [x] Local test matrix: `.venv` (3.11.12), `.venv310` (uv, 3.10.12) and `.venv312`
      (conda `p12`, 3.12.2), all at 64 passed.
- [x] `.gitignore` extended with `.venv*/`, `build/`, `dist/`, `.coverage`, `htmlcov/`,
      `.mypy_cache/`, `.env`, `.idea/`, `.vscode/`, `.DS_Store`.
- [x] `CHANGELOG.md` created with the `2026.9.0` entry.
- [x] Repository description and topics set (`tsetmc`, `codal`, `tgju`, `iran`,
      `bourse`, `finance`, `pandas`, `stock-market`).
- [x] Git repository initialised, first commit made, `origin` wired to
      `github.com/Fazel94/yfinance-ir`. Nothing pushed: the remote reports an empty
      repository.
- [x] `CONTRIBUTING.md`: setup, checks, fixture re-recording, versioning.
- [x] `SECURITY.md`: reporting address and the `verify=False` scope.
- [x] `.github/ISSUE_TEMPLATE/bug_report.yml` asks for network location first.
- [x] `.github/pull_request_template.md`.
- [x] `.github/workflows/ci.yml`: ruff and pytest on 3.9 to 3.13 with
      `-W error::DeprecationWarning`.
- [x] README badges: CI, Python versions (static), MIT.
- [x] README restructured; long passages moved to `docs/conventions.md` and
      `docs/data-sources.md`.

## Published

- [x] Pushed `main` to `github.com/Fazel94/yfinance-ir` (62 files).
- [x] First CI run (`35630922800`) green on 3.9, 3.10, 3.11, 3.12 and 3.13, which also
      proves `requires-python = ">=3.9"`.

## CI

- [ ] Optional `release.yml`: build and publish on tag with PyPI Trusted Publishing, so
      no API token lives in repository secrets.
- [ ] Optional `dependabot.yml` for `pip` and `github-actions`.
- [ ] PyPI version badge after the first upload.

## Documentation

- [ ] Add a financial-data disclaimer beyond the non-affiliation notice if you want the
      accuracy and terms-of-use wording to be separate from it.
- [ ] Keep the as-of claims dated: the CPI base year (1400 = 100), the `ccxt-ir` 4.19.0
      breakage, and the 2026 AGM example in *Non-trading rows*.

## Before tagging a release

- [ ] `ruff check .` clean and `python -m pytest` at 64 passed on every CI Python.
- [ ] `python -m build && twine check dist/*` clean.
- [ ] Wheel installs in a fresh venv, imports, and resolves one symbol.
- [ ] Run `pytest -m live` from an Iranian IP and record the date in the release notes as
      the last confirmation that the upstream endpoints work.
- [ ] Tag `v2026.9.0`, write the GitHub release, then publish to PyPI. The name
      `yfinance-ir` was free on PyPI at audit time.
