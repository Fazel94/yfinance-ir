# TODO

Options for continuing after 2026.9.1, which shipped as a GitHub release only. Cash-flow statements, option chains and intraday bars are done (CHANGELOG, Unreleased).

## Publish to PyPI

Deferred at 2026.9.1. `https://pypi.org/pypi/yfinance-ir/json` returned 404 on 2026-09-24, so the name was free then; nothing reserves it until the first upload.

- [ ] Pick the upload path.
  - Trusted Publishing: add `.github/workflows/release.yml`, triggered by `release: types: [published]`. A build job runs `python -m build` and `twine check dist/*` and stores `dist/` as an artifact; a publish job with `environment: pypi` and `permissions: id-token: write` downloads it and runs `pypa/gh-action-pypi-publish@release/v1`. One-time setup: a pending publisher at <https://pypi.org/manage/account/publishing/> with project `yfinance-ir`, owner `Fazel94`, repository `yfinance-ir`, workflow `release.yml`, environment `pypi`, plus required reviewers on the `pypi` environment. No token is stored anywhere.
  - Manual: `python -m build && twine upload dist/*` with a PyPI API token, by hand for every release.
- [ ] Add a PyPI version badge to the README.
- [ ] Switch the README install lines back to `pip install yfinance-ir`, `pip install "yfinance-ir[crypto]"` and `pip install "yfinance-ir[crypto,notebook]"`, and tick the PyPI line in `PUBLISH_CHECKLIST.md`.
