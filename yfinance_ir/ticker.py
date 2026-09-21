"""``Ticker`` / ``Tickers`` -- the yfinance-shaped façade over TSETMC, Codal and TGJU."""

import datetime as _dt
from typing import Dict, List, Optional, Sequence, Union

import pandas as pd
import requests

from . import fundamentals
from . import history as _history
from ._dates import deven_to_date
from ._http import new_session
from .exceptions import DataUnavailable
from .resolver import Instrument, resolve
from .sources import codal, sci, tsetmc

__all__ = ["Ticker", "Tickers"]

_ORDERBOOK_COLUMNS = [
    "bid_count",
    "bid_volume",
    "bid_price",
    "ask_price",
    "ask_volume",
    "ask_count",
]

_CLIENT_TYPE_COLUMNS = [
    "individual_buy_count",
    "institutional_buy_count",
    "individual_sell_count",
    "institutional_sell_count",
    "individual_buy_volume",
    "institutional_buy_volume",
    "individual_sell_volume",
    "institutional_sell_volume",
    "individual_buy_value",
    "institutional_buy_value",
    "individual_sell_value",
    "institutional_sell_value",
]


def _float(value) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


class Ticker:
    """One instrument. ``Ticker("فولاد")``, ``Ticker("USD")``, ``Ticker("BTC-IRT")``."""

    def __init__(self, symbol: str, session: Optional[requests.Session] = None):
        self.session = session or new_session()
        self.ticker = str(symbol).strip()
        self.instrument: Instrument = resolve(self.session, self.ticker)
        self._info: Optional[dict] = None
        self._history: Dict[tuple, pd.DataFrame] = {}
        self._actions: Optional[tuple] = None

    def __repr__(self) -> str:
        return f"yfinance_ir.Ticker object <{self.instrument.symbol}>"

    # ------------------------------------------------------------------ prices

    def history(self, **kwargs) -> pd.DataFrame:
        key = tuple(sorted((k, str(v)) for k, v in kwargs.items()))
        if key not in self._history:
            self._history[key] = _history.history(self.session, self.instrument, **kwargs)
        return self._history[key].copy()

    def _cached_actions(self):
        if self._actions is None:
            self._actions = _history.fetch_actions(self.session, self.instrument)
        return self._actions

    @property
    def dividends(self) -> pd.Series:
        return self._cached_actions()[0].copy()

    @property
    def splits(self) -> pd.Series:
        return self._cached_actions()[1].copy()

    @property
    def actions(self) -> pd.DataFrame:
        dividends, splits = self._cached_actions()
        frame = pd.concat([dividends, splits], axis=1)
        frame.columns = ["Dividends", "Stock Splits"]
        return frame.fillna(0.0).sort_index()

    # -------------------------------------------------------------------- info

    @property
    def info(self) -> dict:
        if self._info is None:
            self._info = self._build_info()
        return self._info

    def _build_info(self) -> dict:
        instrument = self.instrument
        if instrument.source == "crypto":
            from .sources import crypto

            return crypto.ticker_info(instrument.ins_code)
        if instrument.source == "tgju":
            frame = self.history(period="1mo")
            last = float(frame["Close"].iloc[-1]) if not frame.empty else None
            return {
                "symbol": instrument.symbol,
                "slug": instrument.ins_code,
                "shortName": instrument.symbol,
                "longName": instrument.name,
                "quoteType": instrument.kind,
                "currency": "IRR",
                "exchange": "TGJU",
                "regularMarketPrice": last,
                "previousClose": float(frame["Close"].iloc[-2])
                if len(frame) > 1
                else None,
            }
        if instrument.source == "sci":
            return self._cpi_info()
        if instrument.kind == "INDEX":
            return self._index_info()
        return self._equity_info()

    def _cpi_info(self) -> dict:
        instrument = self.instrument
        _observations, meta = sci.series(self.session, instrument.ins_code)
        frame = self.history(period="max")
        last = frame.iloc[-1] if not frame.empty else None
        return {
            "symbol": instrument.symbol,
            "shortName": instrument.symbol,
            "longName": meta.get("title") or instrument.symbol,
            "quoteType": "MACRO",
            "exchange": "SCI",
            "currency": None,
            "frequency": "monthly",
            "baseYear": meta.get("base_year"),
            "dataset": sci.DATASETS[instrument.ins_code],
            "regularMarketPrice": float(last["Close"]) if last is not None else None,
            "previousClose": float(frame["Close"].iloc[-2]) if len(frame) > 1 else None,
            "monthlyInflation": float(last["MoM"]) if last is not None else None,
            "annualInflation": float(last["YoY"]) if last is not None else None,
            "lastPeriod": frame.index[-1].date() if not frame.empty else None,
        }

    def _index_info(self) -> dict:
        instrument = self.instrument
        row = {}
        for flow in (instrument.flow or 1, 1, 2):
            try:
                rows = tsetmc.indices_all(self.session, flow)
            except DataUnavailable:
                continue
            match = [r for r in rows if str(r.get("insCode")) == instrument.ins_code]
            if match:
                row = match[0]
                break
        return {
            "symbol": instrument.symbol,
            "shortName": instrument.symbol,
            "longName": instrument.name,
            "quoteType": "INDEX",
            "insCode": instrument.ins_code,
            "exchange": "TSETMC",
            "currency": None,
            "regularMarketPrice": _float(row.get("xDrNivJIdx004")),
            "dayHigh": _float(row.get("xPhNivJIdx004")),
            "dayLow": _float(row.get("xPbNivJIdx004")),
            "changePercent": _float(row.get("xVarIdxJRfV")),
            "change": _float(row.get("indexChange")),
        }

    def _equity_info(self) -> dict:
        instrument = self.instrument
        raw = tsetmc.info(self.session, instrument.ins_code) or {}
        quote = tsetmc.closing_price_info(self.session, instrument.ins_code) or {}
        identity = tsetmc.identity(self.session, instrument.ins_code) or {}

        eps_block = raw.get("eps") or {}
        eps = _float(eps_block.get("estimatedEPS")) or _float(eps_block.get("epsValue"))
        shares = _float(raw.get("zTitad"))
        close = _float(quote.get("pClosing"))
        last = _float(quote.get("pDrCotVal"))
        state = ((quote.get("instrumentState") or {}).get("cEtaval") or "").strip()

        info = {
            "symbol": instrument.symbol,
            "shortName": instrument.symbol,
            "longName": instrument.name or raw.get("lVal30"),
            "isin": instrument.isin,
            "insCode": instrument.ins_code,
            "quoteType": instrument.kind,
            "exchange": raw.get("flowTitle") or identity.get("flowTitle") or "TSETMC",
            "market": instrument.market or identity.get("cgrValCotTitle"),
            "sector": ((raw.get("sector") or identity.get("sector") or {}) or {}).get("lSecVal"),
            "industry": ((identity.get("subSector") or {}) or {}).get("lSoSecVal"),
            "currency": "IRR",
            "sharesOutstanding": shares,
            "trailingEps": eps,
            "sectorPE": _float(eps_block.get("sectorPE")),
            "trailingPE": (last / eps) if (eps and last and eps > 0) else None,
            "baseVolume": _float(raw.get("baseVol")),
            "regularMarketPrice": last,
            "regularMarketPreviousClose": _float(quote.get("priceYesterday")),
            "previousClose": _float(quote.get("priceYesterday")),
            "open": _float(quote.get("priceFirst")),
            "dayHigh": _float(quote.get("priceMax")),
            "dayLow": _float(quote.get("priceMin")),
            "close": close,
            "volume": _float(quote.get("qTotTran5J")),
            "regularMarketVolume": _float(quote.get("qTotTran5J")),
            "averageVolume": _float(raw.get("qTotTran5JAvg")),
            "tradeCount": _float(quote.get("zTotTran")),
            "tradeValue": _float(quote.get("qTotCap")),
            "marketCap": (close * shares) if (close and shares) else None,
            "fiftyTwoWeekLow": _float(raw.get("minYear")),
            "fiftyTwoWeekHigh": _float(raw.get("maxYear")),
            "marketState": "REGULAR" if state in {"A", ""} else "HALTED",
            "underSupervision": raw.get("underSupervision"),
            "lastTradeDate": deven_to_date(quote["dEven"]) if quote.get("dEven") else None,
            "lastTradeTime": quote.get("hEven"),
        }
        if instrument.kind == "ETF":
            try:
                fund = tsetmc.etf(self.session, instrument.ins_code) or {}
            except DataUnavailable:
                fund = {}
            if fund:
                # Fund/GetETFByInsCode answers {pRedTran: NAV ابطال, pSubTran: NAV صدور}
                info["navPrice"] = _float(fund.get("pRedTran"))
                info["navRedemption"] = _float(fund.get("pRedTran"))
                info["navSubscription"] = _float(fund.get("pSubTran"))
                info["navDate"] = (
                    deven_to_date(fund["deven"]) if fund.get("deven") else None
                )
        return info

    # ------------------------------------------------------------- market data

    def _require_tsetmc(self, what: str) -> None:
        if not self.instrument.is_tsetmc or self.instrument.kind == "INDEX":
            raise DataUnavailable(0, "", f"{what} is only available for TSETMC instruments")

    @property
    def orderbook(self) -> pd.DataFrame:
        if self.instrument.source == "crypto":
            from .sources import crypto

            return crypto.orderbook(self.instrument.ins_code, _ORDERBOOK_COLUMNS)
        self._require_tsetmc("orderbook")
        rows = tsetmc.best_limits(self.session, self.instrument.ins_code)
        frame = pd.DataFrame(
            [
                {
                    "bid_count": row.get("zOrdMeDem"),
                    "bid_volume": row.get("qTitMeDem"),
                    "bid_price": _float(row.get("pMeDem")),
                    "ask_price": _float(row.get("pMeOf")),
                    "ask_volume": row.get("qTitMeOf"),
                    "ask_count": row.get("zOrdMeOf"),
                }
                for row in rows
            ],
            columns=_ORDERBOOK_COLUMNS,
        )
        frame.index = pd.RangeIndex(1, len(frame) + 1, name="level")
        return frame

    @property
    def client_types(self) -> pd.DataFrame:
        self._require_tsetmc("client_types")
        row = tsetmc.client_type(self.session, self.instrument.ins_code) or {}
        data = {
            "individual_buy_count": row.get("buy_CountI"),
            "institutional_buy_count": row.get("buy_CountN"),
            "individual_sell_count": row.get("sell_CountI"),
            "institutional_sell_count": row.get("sell_CountN"),
            "individual_buy_volume": row.get("buy_I_Volume"),
            "institutional_buy_volume": row.get("buy_N_Volume"),
            "individual_sell_volume": row.get("sell_I_Volume"),
            "institutional_sell_volume": row.get("sell_N_Volume"),
        }
        frame = pd.DataFrame([data], columns=_CLIENT_TYPE_COLUMNS)
        last = self.info.get("lastTradeDate")
        frame.index = pd.DatetimeIndex([pd.Timestamp(last)] if last else [pd.NaT], name="Date")
        return frame

    def client_type_history(self) -> pd.DataFrame:
        """Daily client-type breakdown (legacy ``old.tsetmc.com`` text feed)."""
        self._require_tsetmc("client_type_history")
        text = tsetmc.client_type_history_txt(self.session, self.instrument.ins_code)
        records, index = [], []
        for chunk in text.split(";"):
            fields = chunk.strip().split(",")
            if len(fields) != 13:
                continue
            try:
                day = deven_to_date(fields[0])
                numbers = [float(x) for x in fields[1:]]
            except (ValueError, TypeError):
                continue
            index.append(pd.Timestamp(day))
            records.append(numbers)
        frame = pd.DataFrame(records, columns=_CLIENT_TYPE_COLUMNS)
        frame.index = pd.DatetimeIndex(index, name="Date")
        return frame.sort_index()

    @property
    def major_holders(self) -> pd.DataFrame:
        self._require_tsetmc("major_holders")
        deven = self.info.get("lastTradeDate")
        deven_int = (
            deven.year * 10000 + deven.month * 100 + deven.day
            if isinstance(deven, _dt.date)
            else 0
        )
        rows = tsetmc.shareholders(self.session, self.instrument.ins_code, deven_int)
        frame = pd.DataFrame(
            [
                {
                    "holder": (row.get("shareHolderName") or "").strip(),
                    "shares": _float(row.get("numberOfShares")),
                    "percent": _float(row.get("perOfShares")),
                    "change": _float(row.get("changeAmount")),
                }
                for row in rows
            ],
            columns=["holder", "shares", "percent", "change"],
        )
        return frame.sort_values("percent", ascending=False).reset_index(drop=True)

    @property
    def news(self) -> List[dict]:
        if not self.instrument.is_tsetmc:
            raise DataUnavailable(0, "", "news is only available for TSETMC instruments")
        out: List[dict] = []
        try:
            letters = tsetmc.codal_prepared(self.session, self.instrument.ins_code, 20)
        except DataUnavailable:
            letters = []
        for letter in letters:
            out.append(
                {
                    "title": letter.get("title"),
                    "publisher": letter.get("name"),
                    "publishDate": letter.get("publishDateTime_Gregorian"),
                    "publishDEven": letter.get("publishDateTime_DEven"),
                    "tracingNo": letter.get("tracingNo"),
                    "attachment": letter.get("fileName"),
                    "kind": "codal",
                }
            )
        try:
            messages = tsetmc.messages(self.session, self.instrument.ins_code)
        except DataUnavailable:
            messages = []
        for message in messages:
            out.append(
                {
                    "title": (message.get("tseTitle") or "").strip(),
                    "publisher": "TSETMC",
                    "publishDate": str(message.get("dEven")),
                    "publishDEven": message.get("dEven"),
                    "body": (message.get("tseDesc") or "").strip(),
                    "kind": "supervisor",
                }
            )
        return out

    # ------------------------------------------------------------ fundamentals

    def _require_company(self) -> None:
        if self.instrument.kind not in {"EQUITY", "ETF"}:
            raise DataUnavailable(
                0, "", f"financial statements are not available for {self.instrument.kind}"
            )

    def _statements(self, sheet_id: int, quarterly: bool) -> pd.DataFrame:
        self._require_company()
        return fundamentals.statements(
            self.session, self.instrument.symbol, sheet_id, quarterly=quarterly
        )

    @property
    def income_stmt(self) -> pd.DataFrame:
        return self._statements(codal.SHEET_INCOME, quarterly=False)

    financials = income_stmt

    @property
    def quarterly_income_stmt(self) -> pd.DataFrame:
        return self._statements(codal.SHEET_INCOME, quarterly=True)

    quarterly_financials = quarterly_income_stmt

    @property
    def balance_sheet(self) -> pd.DataFrame:
        return self._statements(codal.SHEET_BALANCE, quarterly=False)

    @property
    def quarterly_balance_sheet(self) -> pd.DataFrame:
        return self._statements(codal.SHEET_BALANCE, quarterly=True)

    def monthly_activity(self, **kwargs) -> pd.DataFrame:
        self._require_company()
        return fundamentals.monthly_activity(self.session, self.instrument.symbol, **kwargs)


class Tickers:
    """``Tickers("فولاد فملی")`` -- a keyed bundle of :class:`Ticker` objects."""

    def __init__(self, tickers: Union[str, Sequence[str]], session: Optional[requests.Session] = None):
        self.session = session or new_session()
        self.symbols = _split_symbols(tickers)
        self.tickers: Dict[str, Ticker] = {
            symbol: Ticker(symbol, session=self.session) for symbol in self.symbols
        }

    def __repr__(self) -> str:
        return f"yfinance_ir.Tickers object <{','.join(self.symbols)}>"

    def history(self, **kwargs) -> pd.DataFrame:
        from .multi import download

        return download(self.symbols, session=self.session, **kwargs)


def _split_symbols(tickers: Union[str, Sequence[str]]) -> List[str]:
    if isinstance(tickers, str):
        parts = [t for t in tickers.replace(",", " ").split() if t]
    else:
        parts = [str(t).strip() for t in tickers if str(t).strip()]
    seen, out = set(), []
    for part in parts:
        if part not in seen:
            seen.add(part)
            out.append(part)
    return out
