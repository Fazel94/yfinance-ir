"""Shared HTTP transport: browser headers, retries, per-host throttle, block detection.

Every network call in this package goes through :func:`get`.
"""

import threading
import time
import warnings
from typing import Dict, Optional
from urllib.parse import urlsplit

import requests
from requests.adapters import HTTPAdapter
from urllib3.exceptions import InsecureRequestWarning
from urllib3.util.retry import Retry

from .config import get_config
from .exceptions import BlockedError, DataUnavailable, RateLimitError

__all__ = ["new_session", "get", "TSETMC_HEADERS", "PLAIN_HEADERS"]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

#: cdn.tsetmc.com rejects requests without a browser UA and wants a tsetmc referer.
TSETMC_HEADERS = {
    "Referer": "https://www.tsetmc.com/",
    "Origin": "https://www.tsetmc.com",
}

#: Codal and TGJU only need the default UA.
PLAIN_HEADERS: Dict[str, str] = {}

#: substrings that mark a WAF / geo-block page rather than real data
_BLOCK_MARKERS = (
    "مسدود",
    "دسترسی شما",
    "request rejected",
    "access denied",
    "cloudflare",
    "General Error Detected",
)

_last_call: Dict[str, float] = {}
_throttle_lock = threading.Lock()


def new_session() -> requests.Session:
    """A :class:`requests.Session` with browser headers and bounded retries."""
    session = requests.Session()
    session.trust_env = get_config().trust_env
    retry = Retry(
        total=3,
        backoff_factor=0.6,
        status_forcelist=(429, 502, 503, 504),
        allowed_methods=("GET",),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "fa,en;q=0.8",
        }
    )
    return session


def _throttle(host: str) -> None:
    gap = get_config().min_interval
    if gap <= 0:
        return
    with _throttle_lock:
        now = time.monotonic()
        previous = _last_call.get(host)
        if previous is not None:
            wait = gap - (now - previous)
            if wait > 0:
                time.sleep(wait)
                now = time.monotonic()
        _last_call[host] = now


def get(
    session: requests.Session,
    url: str,
    *,
    params: Optional[dict] = None,
    host_headers: Optional[Dict[str, str]] = None,
    timeout: Optional[float] = None,
    expect_json: bool = True,
    verify: bool = True,
) -> requests.Response:
    """GET ``url``, raising the package's exceptions instead of returning bad bodies."""
    config = get_config()
    _throttle(urlsplit(url).netloc)
    try:
        with warnings.catch_warnings():
            if not verify:
                # only amar.org.ir needs this: it serves no intermediate certificate
                warnings.simplefilter("ignore", InsecureRequestWarning)
            response = session.get(
                url,
                params=params,
                headers=host_headers or None,
                timeout=timeout or config.timeout,
                verify=verify,
            )
    except requests.Timeout as exc:
        raise DataUnavailable(0, url, f"timeout: {exc}") from exc
    except requests.RequestException as exc:
        raise DataUnavailable(0, url, f"request failed: {exc}") from exc

    if response.status_code == 429:
        raise RateLimitError(f"rate limited by {urlsplit(url).netloc}: {url}")

    content_type = response.headers.get("Content-Type", "")
    # only text payloads can carry a WAF page; decoding a spreadsheet would be waste
    if response.content and (content_type.startswith("text/") or "json" in content_type):
        lowered = response.text[:4000].lower()
        if any(marker.lower() in lowered for marker in _BLOCK_MARKERS):
            raise BlockedError(f"blocked by {urlsplit(url).netloc}: {url}")
    if response.status_code >= 400:
        raise DataUnavailable(response.status_code, url)
    if expect_json and content_type.startswith("text/html"):
        raise BlockedError(f"expected JSON but got HTML from {url}")
    return response
