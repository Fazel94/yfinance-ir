"""فولاد total return in Rial, in USD, and deflated by CPI.

Run with an Iranian IP:

    python examples/real_returns.py [period]

TGJU quotes the dollar in Rial per USD on trading days; the SCI CPI is one level per
Jalali month, stamped on the month's first day. Both are forward-filled onto فولاد's
trading calendar, so a bar carries the last published dollar rate and the CPI of the
month it falls in.
"""

import sys

import pandas as pd

import yfinance_ir as yf

period = sys.argv[1] if len(sys.argv) > 1 else "5y"

folad = yf.Ticker("فولاد").history(period=period)["Close"]
usd = yf.Ticker("USD").history(period=period)["Close"]
cpi = yf.Ticker("CPI").history(period=period)["Close"]

usd = usd.reindex(folad.index, method="ffill")
cpi = cpi.reindex(folad.index, method="ffill")

frame = pd.DataFrame(
    {
        "Rial": folad,
        "USD": folad / usd,
        "Real": folad / cpi * cpi.iloc[-1],  # Rial of the latest CPI month
    }
).dropna()

first, last = frame.index[0].date(), frame.index[-1].date()
total = frame.iloc[-1] / frame.iloc[0] - 1
years = (frame.index[-1] - frame.index[0]).days / 365.25
annual = (1 + total) ** (1 / years) - 1

print(f"فولاد {first} -> {last} ({years:.1f}y)")
print(pd.DataFrame({"total": total, "annualised": annual}).map("{:+.1%}".format))
