"""Symbol -> :class:`Instrument` resolution with a persistent sqlite cache.

Resolution order (first hit wins):

1. cache
2. ``BTC-IRT`` / ``BTC-USDT`` style pairs -> crypto (no network, not cached)
3. a TGJU alias (``USD``, ``GOLD18``, ``COIN``...) or a bare ``[a-z0-9_]+`` TGJU slug
4. a bare 10..20 digit InsCode
5. an ISIN -- only resolvable from the local cache, see below
6. a TSETMC symbol (``lVal18AFC`` exact match after normalisation)
7. a TSETMC index name (``lVal30`` of ``GetIndexB1LastAll``)

Deviations from the original design, forced by what the upstream actually does
(probed 2026-09-20):

* ``GetInstrumentSearch`` answers with ``cIsin: null`` and only accepts Persian text --
  ``search("IRO1FOLD0009")``, ``search("FOLD")`` and the official ISIN-keyed
  ``webgw.tse.ir`` gateway all return nothing (the latter is WAF-blocked). So an ISIN can
  only be mapped back to an instrument if that instrument was resolved before and is in
  the local cache; otherwise :class:`~yfinance_ir.exceptions.SymbolNotFound` is raised
  with an explanation.
* Because ``cIsin`` is missing from search results, the chosen row is always confirmed
  with ``GetInstrumentIdentity``, which supplies the ISIN, the canonical name and the
  market title used for the EQUITY/ETF/BOND/OPTION classification.
* Symbol search is tried *before* the index list: no equity symbol is also an index
  name, and searching first saves two full index downloads per resolution.
"""

import re
import unicodedata
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import requests

from . import _cache
from .exceptions import DataUnavailable, SymbolNotFound
from .sources import sci, tgju, tsetmc

__all__ = ["Instrument", "normalize", "resolve"]

_ARABIC_MAP = {
    ord("ي"): "ی",
    ord("ك"): "ک",
    ord("ة"): "ه",
    ord("\u200f"): "",
    ord("\u200e"): "",
}
_ZWNJ = "\u200c"

_CRYPTO_RE = re.compile(r"^[A-Z0-9]{2,10}-(IRT|USDT|RLS)$")
_INS_RE = re.compile(r"^\d{10,20}$")
_ISIN_RE = re.compile(r"^IR[A-Z0-9]{10}$")


def normalize(text: str, *, strip_zwnj: bool = True) -> str:
    """NFKC + Arabic/Persian letter unification + whitespace squeeze.

    ZWNJ is removed by default so that ``فولاد مبارکه`` matches whichever way the
    upstream typed it; pass ``strip_zwnj=False`` to keep human-readable labels intact.
    """
    if text is None:
        return ""
    out = unicodedata.normalize("NFKC", str(text)).translate(_ARABIC_MAP)
    if strip_zwnj:
        out = out.replace(_ZWNJ, "")
    else:
        out = out.replace(_ZWNJ, "\u200c")
    return " ".join(out.split()).strip()


@dataclass
class Instrument:
    ins_code: str
    symbol: str
    name: str = ""
    isin: Optional[str] = None
    flow: int = 0
    kind: str = "EQUITY"  # EQUITY|ETF|INDEX|BOND|OPTION|CURRENCY|COMMODITY|CRYPTO
    source: str = "tsetmc"  # tsetmc|tgju|crypto
    alt_ins_codes: Tuple[str, ...] = field(default_factory=tuple)
    market: str = ""

    @property
    def is_tsetmc(self) -> bool:
        return self.source == "tsetmc"


def _kind_from(isin: Optional[str], market_title: str, group_code: str = "") -> str:
    market_title = market_title or ""
    if "صندوق" in market_title:
        return "ETF"
    code = (isin or "")[:4].upper()
    if code in {"IRT1", "IRT3"}:
        return "ETF"
    if code.startswith("IRB"):
        return "BOND"
    if code in {"IRO9"} or code.startswith("IRS"):
        return "OPTION"
    if (group_code or "").startswith("6"):
        return "OPTION"
    return "EQUITY"


def _from_cache_row(row: dict) -> Instrument:
    return Instrument(
        ins_code=row["ins_code"],
        symbol=row["symbol"],
        name=row["name"] or "",
        isin=row["isin"],
        flow=row["flow"] or 0,
        kind=row["kind"] or "EQUITY",
        source=row["source"] or "tsetmc",
        alt_ins_codes=tuple(row["alt_ins_codes"]),
    )


def _crypto_instrument(query: str) -> Instrument:
    pair = query.upper()
    return Instrument(
        ins_code=pair,
        symbol=pair,
        name=pair,
        isin=None,
        flow=0,
        kind="CRYPTO",
        source="crypto",
    )


def _tgju_instrument(query: str, slug: str) -> Instrument:
    return Instrument(
        ins_code=slug,
        symbol=query.upper(),
        name=slug,
        isin=None,
        flow=0,
        kind="CURRENCY" if slug.startswith("price_") else "COMMODITY",
        source="tgju",
    )


def _sci_instrument(alias: str) -> Instrument:
    alias = alias.upper()
    return Instrument(
        ins_code=alias,
        symbol=alias,
        name=sci.DATASETS[alias],
        isin=None,
        flow=0,
        kind="MACRO",
        source="sci",
    )


def _instrument_from_ins(session: requests.Session, ins_code: str, alts=()) -> Instrument:
    identity = tsetmc.identity(session, ins_code)
    if not identity:
        raise SymbolNotFound(ins_code)
    isin = identity.get("cIsin")
    return Instrument(
        ins_code=str(ins_code),
        symbol=normalize(identity.get("lVal18AFC") or ins_code),
        name=normalize(identity.get("lVal30") or ""),
        isin=isin,
        flow=int(identity.get("flow") or 0),
        kind=_kind_from(isin, identity.get("cgrValCotTitle") or "", identity.get("cgrValCot") or ""),
        source="tsetmc",
        alt_ins_codes=tuple(str(a) for a in alts),
        market=normalize(identity.get("cgrValCotTitle") or ""),
    )


def _last_trade_deven(session: requests.Session, ins_code: str) -> int:
    try:
        return int(tsetmc.closing_price_info(session, ins_code).get("dEven") or 0)
    except DataUnavailable:
        return 0


def _match_symbol(session: requests.Session, key: str) -> Optional[Instrument]:
    rows = tsetmc.search(session, key)
    exact: List[dict] = [r for r in rows if normalize(r.get("lVal18AFC")) == key]
    if not exact:
        return None
    if len(exact) == 1:
        primary, alts = exact[0], []
    else:
        ranked = sorted(exact, key=lambda r: _last_trade_deven(session, str(r["insCode"])), reverse=True)
        primary, alts = ranked[0], ranked[1:]
    return _instrument_from_ins(
        session,
        str(primary["insCode"]),
        alts=[str(r["insCode"]) for r in alts],
    )


def _match_index(session: requests.Session, key: str) -> Optional[Instrument]:
    for flow in (1, 2):
        try:
            rows = tsetmc.indices_all(session, flow)
        except DataUnavailable:
            continue
        for row in rows:
            if normalize(row.get("lVal30")) == key:
                return Instrument(
                    ins_code=str(row["insCode"]),
                    symbol=key,
                    name=normalize(row.get("lVal30")),
                    isin=None,
                    flow=flow,
                    kind="INDEX",
                    source="tsetmc",
                )
    return None


def resolve(session: requests.Session, query: str, *, use_cache: bool = True) -> Instrument:
    if query is None or not str(query).strip():
        raise SymbolNotFound(str(query))
    raw = str(query).strip()
    key = normalize(raw)

    if _CRYPTO_RE.match(raw.upper()):
        return _crypto_instrument(raw)

    cache = _cache.get_cache()
    if use_cache:
        row = cache.get(key)
        if row is not None:
            return _from_cache_row(row)

    if raw.upper() in sci.DATASETS:
        instrument = _sci_instrument(raw)
        cache.put(key, instrument)
        return instrument

    slug = tgju.slug_for(raw) if not _INS_RE.match(raw) else None
    if slug is not None and (raw.upper() in tgju.ALIASES or re.match(r"^[a-z0-9_]+$", raw)):
        instrument = _tgju_instrument(raw, slug)
        cache.put(key, instrument)
        return instrument

    if _INS_RE.match(raw):
        instrument = _instrument_from_ins(session, raw)
        cache.put(key, instrument)
        cache.put(normalize(instrument.symbol), instrument)
        return instrument

    if _ISIN_RE.match(raw.upper()):
        row = cache.get_by_isin(raw.upper())
        if row is not None:
            return _from_cache_row(row)
        raise SymbolNotFound(
            f"{raw} (TSETMC search does not accept ISINs; resolve the Persian symbol once "
            "so the ISIN lands in the local cache, then look it up by ISIN)"
        )

    instrument = _match_symbol(session, key) or _match_index(session, key)
    if instrument is None:
        raise SymbolNotFound(raw)
    cache.put(key, instrument)
    return instrument
