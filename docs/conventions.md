# Conventions

How yfinance-ir shapes the data it returns. The README summarises these in one line each.

## Prices

TSETMC and TGJU are Rial. Crypto pairs quoted `*-IRT` are Toman (Nobitex's `/v3/orderbook`
actually answers in Rial; it is rescaled so one instrument never mixes units).

## Columns

`Open High Low Close Volume Dividends "Stock Splits"`, plus TSETMC-only
`Last` (آخرین معامله, distinct from `Close` = قیمت پایانی), `Value` and `Count`.
`auto_adjust=False` inserts `Adj Close` and leaves the price columns raw.

## Dates

The index is a Gregorian `DatetimeIndex`. `start`/`end` accept Gregorian
`YYYY-MM-DD`, Jalali `1403-01-01` (year < 1700 is read as Jalali), `dEven` ints and
`date`/`datetime`. `end` is exclusive. `history(jalali=True)` adds a `JDate` column.
`period` accepts `1d 5d 1mo 3mo 6mo 1y 2y 5y 10y ytd max` (`ytd` = since 1 Farvardin).

## Adjustment

TSETMC publishes no adjusted series. `GetPriceAdjustList` gives, per
corporate event, the previous close both adjusted and unadjusted; every bar strictly
before an ex-date is multiplied by `adjusted / unadjusted`, so a bar's factor is the
product of all later events' ratios. The cash difference becomes `Dividends` on the
ex-date, unless a share-count change lands within ±3 days, which makes it a capital
increase and produces `Stock Splits = numberOfShareNew / numberOfShareOld`.

`GetPriceAdjustList` covers dividends and little else. For فولاد it holds 23 dividend
rows and one 2019 capital increase, while `GetInstrumentShareChange` records the share
count going 209B to 1,935B between 2020 and 2026. Every share change with no adjust row
within ±3 days is therefore treated as a bonus issue: `Stock Splits = new / old` on its
date and every earlier bar multiplied by `old / new`. That is exact for increases paid
from retained earnings or reserves and over-adjusts a rights issue paid in cash, since
TSETMC does not say which kind an increase was.

An ex-date is usually a halted, bar-less day, so `Dividends` and `Stock Splits` land on
the first bar at or after it; `Ticker.dividends` and `Ticker.splits` keep the raw dates.

## Non-trading rows

TSETMC returns calendar rows with zero volume and zero trades while
a symbol is suspended (e.g. فولاد was frozen at 2604 for the three weeks before its 2026
AGM). Those are dropped, so a gap in the index means "no trading", not "missing data".

## Errors

Errors are typed: `SymbolNotFound`, `BlockedError` (WAF/geo-block page instead of data),
`RateLimitError` (429 after retries) and `DataUnavailable` (endpoint has nothing for this
instrument). All four subclass `YFIRError`.
