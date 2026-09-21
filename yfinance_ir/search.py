"""``Search("فولاد")`` -- yfinance-shaped symbol lookup over TSETMC's search endpoint."""

from typing import List, Optional

import requests

from ._http import new_session
from .resolver import normalize
from .sources import tsetmc

__all__ = ["Search"]


class Search:
    def __init__(self, query: str, max_results: int = 10, session: Optional[requests.Session] = None):
        self.query = str(query).strip()
        self.max_results = max_results
        self.session = session or new_session()
        self._quotes: Optional[List[dict]] = None

    def __repr__(self) -> str:
        return f"yfinance_ir.Search object <{self.query}>"

    @property
    def quotes(self) -> List[dict]:
        if self._quotes is None:
            rows = tsetmc.search(self.session, self.query)
            seen, out = set(), []
            for row in rows:
                ins_code = str(row.get("insCode"))
                if ins_code in seen:
                    continue
                seen.add(ins_code)
                out.append(
                    {
                        "symbol": normalize(row.get("lVal18AFC")),
                        "name": normalize(row.get("lVal30")),
                        "insCode": ins_code,
                        "isin": row.get("cIsin"),
                        "exchange": row.get("flowTitle"),
                        "market": row.get("cgrValCotTitle"),
                    }
                )
                if len(out) >= self.max_results:
                    break
            self._quotes = out
        return self._quotes

    @property
    def all(self) -> dict:
        return {"quotes": self.quotes}
