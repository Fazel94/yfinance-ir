"""Optional crypto bridge over ``ccxt-ir`` (nobitex, wallex, ramzinex, tabdeal, bitpin...).

``ccxt-ir`` supplies market discovery and ``fetch_ticker``, so
``pip install yfinance-ir[crypto]`` remains the whole install story. Two of its unified
methods are broken in the pinned release and are routed around here:

* ``fetch_ohlcv`` raises ``NameError: name 'Date' is not defined`` on **every** ccxt-ir
  exchange (4.19.0 ships an untranspiled ``Date.now()``), and
* ``fetch_order_book`` raises ``TypeError: unsupported operand type(s) for /: 'str'``.

So OHLCV and depth fall back to Nobitex's public REST API, whose base URL is read from
ccxt's own ``urls["api"]["public"]`` (``https://apiv2.nobitex.ir``) instead of being
hardcoded: ``/market/udf/history`` (TradingView UDF; Rial prices, same scale as
``fetch_ticker``) and ``/v3/orderbook/{PAIR}``. The UDF pair id is ``BTCIRT``-style,
which is *not* ccxt's market id (``btc-rls``), so it is rebuilt from base/quote.
A non-Nobitex exchange re-raises the original ccxt error rather than guessing at its API.
"""

import datetime as _dt
from typing import Dict, List, Optional

import pandas as pd

from .._http import get, new_session
from ..config import get_config
from ..exceptions import DataUnavailable, SymbolNotFound

__all__ = ["ohlcv", "ticker_info", "orderbook", "exchange_for", "to_ccxt_symbol"]

_INSTALL_HINT = "crypto support requires: pip install yfinance-ir[crypto]"
_DEFAULT_SINCE = _dt.date(2018, 1, 1)
_RIAL_QUOTES = {"IRT", "IRR", "RLS"}
_UDF_RESOLUTION = {"1d": "D", "1h": "60", "1m": "1"}

_exchanges: Dict[str, object] = {}


def _ccxt():
    try:
        import ccxt  # noqa: F401  (ccxt-ir installs under the `ccxt` import name)
    except ImportError as exc:
        raise DataUnavailable(0, "", _INSTALL_HINT) from exc
    return ccxt


def exchange_for(name: Optional[str] = None):
    """Build (once per process) the configured ccxt-ir exchange client."""
    ccxt = _ccxt()
    name = name or get_config().crypto_exchange
    if name not in _exchanges:
        factory = getattr(ccxt, name, None)
        if factory is None:
            raise DataUnavailable(0, "", f"ccxt-ir has no exchange named {name!r}")
        _exchanges[name] = factory({"enableRateLimit": True})
    return _exchanges[name]


def to_ccxt_symbol(pair: str) -> str:
    return pair.upper().replace("-", "/", 1)


def _require_market(client, symbol: str, pair: str) -> str:
    markets = client.load_markets()
    if symbol in markets:
        return symbol
    base, _, quote = symbol.partition("/")
    for alias in (f"{base}/IRT", f"{base}/IRR", f"{base}/RLS"):
        if quote in _RIAL_QUOTES and alias in markets:
            return alias
    raise SymbolNotFound(f"{pair} (not listed on {client.id})")


def _public_base(client) -> str:
    api = client.urls.get("api")
    url = api.get("public") if isinstance(api, dict) else api
    if not url:
        raise DataUnavailable(0, "", f"{client.id} exposes no public REST base url")
    return str(url).rstrip("/")


def _udf_pair(client, symbol: str) -> str:
    market = client.market(symbol)
    base = (market.get("base") or symbol.partition("/")[0]).upper()
    quote = (market.get("quote") or symbol.partition("/")[2]).upper()
    return base + ("IRT" if quote in _RIAL_QUOTES else quote)


def _nobitex_only(client, exc: Exception) -> None:
    if client.id != "nobitex":
        raise exc


def _udf_ohlcv(client, symbol: str, since_ms: int, timeframe: str) -> List[list]:
    resolution = _UDF_RESOLUTION.get(timeframe)
    if resolution is None:
        raise DataUnavailable(0, "", f"unsupported crypto timeframe: {timeframe!r}")
    params = {
        "symbol": _udf_pair(client, symbol),
        "resolution": resolution,
        "from": since_ms // 1000,
        "to": int(_dt.datetime.now().timestamp()),
    }
    payload = get(new_session(), f"{_public_base(client)}/market/udf/history", params=params).json()
    if payload.get("s") != "ok" or not payload.get("t"):
        return []
    return [
        [int(t) * 1000, float(o), float(h), float(low), float(c), float(v)]
        for t, o, h, low, c, v in zip(
            payload["t"], payload["o"], payload["h"], payload["l"], payload["c"], payload["v"]
        )
    ]


def ohlcv(
    pair: str,
    *,
    since: Optional[_dt.date] = None,
    timeframe: str = "1d",
    limit: int = 1000,
) -> List[list]:
    """Paged ``[ts_ms, open, high, low, close, volume]`` rows, ascending."""
    client = exchange_for()
    symbol = _require_market(client, to_ccxt_symbol(pair), pair)
    start = since or _DEFAULT_SINCE
    since_ms = int(_dt.datetime(start.year, start.month, start.day).timestamp() * 1000)
    now_ms = int(_dt.datetime.now().timestamp() * 1000)

    rows: List[list] = []
    seen = set()
    cursor = since_ms
    while True:
        try:
            page = client.fetch_ohlcv(symbol, timeframe, cursor, limit)
        except (NameError, TypeError, AttributeError) as exc:  # ccxt-ir transpilation bugs
            _nobitex_only(client, exc)
            return _udf_ohlcv(client, symbol, since_ms, timeframe)
        if not page:
            break
        for candle in page:
            if candle[0] not in seen:
                seen.add(candle[0])
                rows.append(list(candle))
        last_ts = page[-1][0]
        if len(page) < limit or last_ts >= now_ms or last_ts < cursor:
            break
        cursor = last_ts + 1
    rows.sort(key=lambda row: row[0])
    return rows


def ticker_info(pair: str) -> dict:
    client = exchange_for()
    symbol = _require_market(client, to_ccxt_symbol(pair), pair)
    quote = client.fetch_ticker(symbol)
    return {
        "symbol": pair.upper(),
        "shortName": pair.upper(),
        "longName": symbol,
        "quoteType": "CRYPTOCURRENCY",
        "exchange": client.id,
        "currency": symbol.partition("/")[2],
        "regularMarketPrice": quote.get("last"),
        "bid": quote.get("bid"),
        "ask": quote.get("ask"),
        "dayHigh": quote.get("high"),
        "dayLow": quote.get("low"),
        "open": quote.get("open"),
        "volume": quote.get("baseVolume"),
        "previousClose": quote.get("previousClose"),
    }


def _rest_orderbook(client, symbol: str, depth: int):
    """Nobitex ``/v3/orderbook`` quotes an ``*-IRT`` pair in **Rial**, while both
    ``fetch_ticker`` and the UDF history quote it in **Toman**; rescale so one
    instrument never mixes units."""
    url = f"{_public_base(client)}/v3/orderbook/{_udf_pair(client, symbol)}"
    payload = get(new_session(), url).json()
    scale = 10.0 if symbol.partition("/")[2].upper() in _RIAL_QUOTES else 1.0
    bids = [[float(p) / scale, float(q)] for p, q in (payload.get("bids") or [])][:depth]
    asks = [[float(p) / scale, float(q)] for p, q in (payload.get("asks") or [])][:depth]
    return bids, asks


def orderbook(pair: str, columns: List[str], depth: int = 5) -> pd.DataFrame:
    client = exchange_for()
    symbol = _require_market(client, to_ccxt_symbol(pair), pair)
    try:
        book = client.fetch_order_book(symbol, limit=depth)
        bids, asks = book.get("bids") or [], book.get("asks") or []
    except (NameError, TypeError, AttributeError) as exc:  # ccxt-ir transpilation bugs
        _nobitex_only(client, exc)
        bids, asks = _rest_orderbook(client, symbol, depth)

    rows = []
    for level in range(max(len(bids), len(asks))):
        bid = bids[level] if level < len(bids) else (None, None)
        ask = asks[level] if level < len(asks) else (None, None)
        rows.append(
            {
                "bid_count": None,
                "bid_volume": bid[1],
                "bid_price": bid[0],
                "ask_price": ask[0],
                "ask_volume": ask[1],
                "ask_count": None,
            }
        )
    frame = pd.DataFrame(rows, columns=columns)
    frame.index = pd.RangeIndex(1, len(frame) + 1, name="level")
    return frame
