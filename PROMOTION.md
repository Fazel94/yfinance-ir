# Promotion checklist

Audit date 2026-10-11. Audience: Persian-first. Install path: GitHub release tags.

`[x]` is done, `[ ]` is open.

## Repository

- [x] `## Compared with other packages` in `README.md`, checked against the three competitor
      READMEs on 2026-10-11 (evidence below).
- [x] `README.fa.md`, linked as `[فارسی]` from the top of `README.md`.
- [x] Topics: 16 (`python`, `tehran-stock-exchange`, `tehran-stocks`, `market-data`,
      `financial-data`, `stocks`, `yfinance`, `jalali` added to the original 8).
- [x] Discussions enabled (default categories: Q&A, Show and tell, Ideas).
- [x] `examples/scoreboard.ipynb` writes `examples/scoreboard_social.png`, 1280 × 640.
- [ ] Social preview: upload `examples/scoreboard_social.png` at
      github.com/Fazel94/yfinance-ir/settings → Social preview → Edit → Upload an image.
      Check: paste the repo URL into Telegram "Saved Messages", the preview shows the card.
- [ ] Telegram channel link added to `README.md` (under the hero chart) and
      `README.fa.md` (`## بروزرسانی ماهانه`) once the channel exists.

## Launch

- [ ] Virgool article «دریافت داده‌های بورس، دلار، طلا و تورم در پایتون با یک API یکسان:
      yfinance-ir», every code block run on publish day from an Iranian IP.
      URL:
- [ ] Telegram channel `@yfinance_ir` (fallback `@yfinanceir`), title
      `yfinance-ir · داده‌های بازار ایران در پایتون`; first post the card + Telegram caption,
      pinned; second post the Virgool URL.
      URL:
- [ ] `@PyFarsi` group: one message (what it is, Iranian-IP note, `pip install` line,
      Virgool URL, repo URL, `scoreboard_linkedin.png`) after reading the pinned rules;
      answer in-thread for 48 h; never repost the monthly card there.
      URL:
- [ ] `@PSFarsi` admins asked to repost the Virgool article (confirm the contact first).
      URL:
- [ ] X thread from [@_fazel94](https://x.com/_fazel94): (1) card + X caption, pinned;
      (2) screenshot of the six Quickstart lines + «یک API برای TSETMC، کدال، TGJU و مرکز
      آمار؛ همان شکل yfinance»; (3) repo URL + Virgool URL + «فقط با IP ایران». Bio links
      the repo.
      URL:
- [x] awesome-quant PR, `Add yfinance-ir (Iranian markets: TSETMC, Codal, TGJU, SCI CPI)`,
      entry after `swiss-finance-data` under `## Market Data & Data Sources`. No follow-up if
      it sits. Opened 2026-10-11.
      URL: https://github.com/wilsonfreitas/awesome-quant/pull/789
- [x] yfinance Discussions → Show and tell, `yfinance-ir: the yfinance API shape for
      Iranian markets (TSETMC, Codal, TGJU, CPI)`. Posted 2026-10-11.
      URL: https://github.com/ranaroussi/yfinance/discussions/2993

LinkedIn is optional: cross-post the monthly card with the Telegram caption and the repo
link in the body. Not a launch item.

## Monthly scoreboard

Trigger: the Statistical Centre of Iran publishes the previous Jalali month's CPI (news on amar.org.ir,
typically in the first week of the next month). Run on that day, from an Iranian IP, in this directory:

1. If the announced month is not yet in SCI's workbook, add it to `SCI_REPORTED` in cell 5 of
   `examples/scoreboard.ipynb`: the dict is `{(jalali_year, jalali_month): index_level}`, e.g.
   `SCI_REPORTED = {(1405, 6): 729.8, (1405, 7): <level>}`. Keep earlier entries; the notebook prefers
   the workbook once it carries the month.
2. Execute headlessly (kernel `yfir312` is registered and `.venv312` has nbconvert 7.17.1, matplotlib
   3.11.2, seaborn, arabic-reshaper, python-bidi, ccxt 4.20.0 and yfinance_ir):
   `cd examples && ../.venv312/bin/python -m nbconvert --to notebook --execute --inplace --ExecutePreprocessor.timeout=1800 scoreboard.ipynb`
   Expected: exit 0; `scoreboard.png`, `scoreboard_linkedin.png`, `scoreboard_social.png` rewritten
   (check `ls -l --time-style=+%F examples/*.png`). A source that fails drops its row and prints why; if
   TSETMC's CDN fails on every asset, rerun later the same day rather than posting a partial board.
3. Read the new card: note inflation %, dollar %, the top asset, the bottom asset, the counts of green and
   red bars, and the one asset that moved most against last month's card (compare with the previous
   `scoreboard_linkedin.png` in git: `git show HEAD:examples/scoreboard_linkedin.png > /tmp/prev.png`).
4. Commit: `git add examples/scoreboard.ipynb examples/scoreboard.png examples/scoreboard_linkedin.png examples/scoreboard_social.png && git commit -m "Scoreboard: <Jalali month> <year>" && git push`.
5. Post in this order, same day: Telegram channel (card `scoreboard_linkedin.png` + Telegram caption),
   X (card + X caption as the first post of a two-post thread, second post = the GitHub link), optional
   LinkedIn (same card and caption, link in the body).
6. Re-upload `scoreboard_social.png` as the GitHub social preview (see `## Repository`).
7. Append the row to the `## Monthly scoreboard` table in `PROMOTION.md`.

| month | run date | SCI_REPORTED entry | commit | Telegram | X |
|---|---|---|---|---|---|

## Caption templates

Telegram caption (fill the braces from the card; keep under 1024 characters so it stays attached to
the photo):

```
📊 از نوروز {سال} تا {تاریخ کارت}: کدام دارایی از تورم و دلار جلو زد؟

تورم {تورم٪} · دلار {دلار٪}
🟢 جلوتر از هر دو: {نام‌های سبز}
🟡 فقط جلوتر از تورم: {نام‌های زرد}
🔴 عقب از هر دو: {نام‌های قرمز}

نسبت به ماه قبل: {یک جمله دربارهٔ بزرگ‌ترین جابه‌جایی}

همهٔ اعداد با یک فراخوانی history() در yfinance-ir (TSETMC، TGJU، مرکز آمار، نوبیتکس)، قیمت‌ها تعدیل‌شده.
کد و نوت‌بوک: github.com/Fazel94/yfinance-ir
```

X caption (first post, ≤ 280 characters with the card attached; second post is the bare repo link):

```
از نوروز {سال} تا {تاریخ}: تورم {تورم٪}، دلار {دلار٪}.
{برندهٔ اول} {بازده٪} جلوتر از هر دو؛ {بازندهٔ آخر} {بازده٪} عقب از هر دو.
{یک جمله دربارهٔ جابه‌جایی ماه}
یک تابع، چهار منبع داده، پایتون: yfinance-ir 👇
```

## Comparison evidence

Checked 2026-10-11 against each README; last-commit months from
`https://api.github.com/repos/<owner>/<repo>/commits?per_page=1`, licences from the GitHub API.

- pytse-client (raw.githubusercontent.com/Glyphack/pytse-client/master/README.md):
  `tse.download(symbols=...)`, `ticker.history`, `برای دریافت قیمت‌های تعدیل شده از adjust=True`,
  `دریافت orderbook با پنج مظنه برتر`, `اطلاعات حقیقی و حقوقی`,
  `tse.get_trade_details(symbol, start_date, end_date, ..., timeframe='1m')` with
  `گزینه‌های معتبر شامل "30s"، "1m"، "5m"، "10m"، "15m"، "30m" و "1h"` (bars), and
  `ticker.get_trade_details()` (ریز معاملات آخرین روز معاملاتی),
  `FinancialIndex(symbol="شاخص کل").history`, `include_jdate=True`. GPL-3.0; last commit
  2025-03-15.
- finpy-tse (raw.githubusercontent.com/ARahimiQuant/finpy-tse/main/README.md):
  `Get_Price_History(... adjust_price ...)`,
  `قابلیت انجام تعدیل قیمت به صورت یکجا با احتساب انواع افزایش سرمایه و پرداخت سود نقدی`,
  `Get_IntradayTrades_History`, `Get_IntradayOB_History`, `Get_RI_History`, `Get_CWI_History`,
  `Get_EWI_History`, `Get_SectorIndex_History`, `Get_USD_RIAL`
  (`قابلیت دسترسی به سابقه ۱۰ ساله قیمت دلار بازار آزاد`; the README does not name the
  dollar's source), `jalali_date=True`. BSD-3-Clause; last commit 2024-04-24.
- tehran-stocks (raw.githubusercontent.com/ghodsizadeh/tehran-stocks/master/README.md):
  `A python package that helps to access TSETMC stock price history`, `Stocks` SQLAlchemy
  model, `ts-get` CLI, `get_dividend()`, `get_shares_history()`, `[x] Jalali Support`. MIT;
  last commit 2023-10-19 (`pushed_at` 2026-04 is not a commit).

Two cells differ from the 2026-10-11 draft: pytse-client's intraday cell (the README
documents `30s`–`1h` bars from trade details, not only the last day's trades) and
finpy-tse's sources (free-market dollar; TGJU is not named).

## Traffic

Run from the repo root on launch day, then weekly for 8 weeks:
`gh api repos/Fazel94/yfinance-ir/traffic/views --jq '{count,uniques}'`,
`gh api repos/Fazel94/yfinance-ir/traffic/clones --jq '{count,uniques}'`,
`gh api repos/Fazel94/yfinance-ir/traffic/popular/referrers --jq '.[:5]'`,
`gh api repos/Fazel94/yfinance-ir --jq .stargazers_count`. There is no PyPI download
counter; unique cloners is the install metric.

| date | views | uniques | clones | unique cloners | stars | top referrers |
|---|---|---|---|---|---|---|
| 2026-10-11 (baseline, 14-day window) | 30 | 17 | 58 | 41 | 2 | github.com 3, com.linkedin.android 2, DuckDuckGo 2, fin-nlogn-ir.pages.dev 1, linkedin.com 1 |
