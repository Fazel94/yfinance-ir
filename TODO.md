# TODO

Options for continuing after 2026.9.2, which shipped as a GitHub release only. Cash-flow statements, option chains and intraday bars shipped in 2026.9.2.
- [ ] check implementing this features as extension of yfinance or adding yfinance as dependency
## Publish to PyPI

Published `2026.9.2` to PyPI on 2026-11-13 by manual `twine upload`: <https://pypi.org/project/yfinance-ir/>.

- [x] Pick the upload path: manual for 2026.9.2. Trusted Publishing is still open for later releases.
  - Trusted Publishing: add `.github/workflows/release.yml`, triggered by `release: types: [published]`. A build job runs `python -m build` and `twine check dist/*` and stores `dist/` as an artifact; a publish job with `environment: pypi` and `permissions: id-token: write` downloads it and runs `pypa/gh-action-pypi-publish@release/v1`. One-time setup: a pending publisher at <https://pypi.org/manage/account/publishing/> with project `yfinance-ir`, owner `Fazel94`, repository `yfinance-ir`, workflow `release.yml`, environment `pypi`, plus required reviewers on the `pypi` environment. No token is stored anywhere.
  - Manual: `python -m build && twine upload dist/*` with a PyPI API token, by hand for every release.
- [x] Add a PyPI version badge to the README.
- [x] Switch the README install lines back to `pip install yfinance-ir`, `pip install "yfinance-ir[crypto]"` and `pip install "yfinance-ir[crypto,notebook]"`, and tick the PyPI line in `PUBLISH_CHECKLIST.md`.
