import time

import pytest
import responses

from yfinance_ir._http import get, new_session
from yfinance_ir.config import set_config
from yfinance_ir.exceptions import BlockedError, DataUnavailable, RateLimitError

URL = "https://cdn.tsetmc.com/api/Instrument/GetInstrumentSearch/x"


@responses.activate
def test_a_waf_page_is_a_blocked_error_not_json_garbage():
    responses.add(responses.GET, URL, body="<html>دسترسی شما به این صفحه مسدود است</html>",
                  content_type="text/html", status=200)

    with pytest.raises(BlockedError):
        get(new_session(), URL)


@responses.activate
def test_unexpected_html_on_a_json_endpoint_is_blocked():
    responses.add(responses.GET, URL, body="<html><body>login</body></html>",
                  content_type="text/html; charset=utf-8", status=200)

    with pytest.raises(BlockedError):
        get(new_session(), URL)


@responses.activate
def test_persistent_429_becomes_a_rate_limit_error():
    for _ in range(5):
        responses.add(responses.GET, URL, json={}, status=429)

    with pytest.raises(RateLimitError):
        get(new_session(), URL)


@responses.activate
def test_http_500_is_data_unavailable_with_the_status_attached():
    responses.add(responses.GET, URL, json={}, status=500)

    with pytest.raises(DataUnavailable) as excinfo:
        get(new_session(), URL)
    assert excinfo.value.status == 500


@responses.activate
def test_html_is_allowed_when_the_caller_does_not_expect_json():
    responses.add(responses.GET, URL, body="<html>ok</html>", content_type="text/html", status=200)

    assert get(new_session(), URL, expect_json=False).text == "<html>ok</html>"


@responses.activate
def test_requests_to_one_host_are_throttled():
    set_config(min_interval=0.2)
    try:
        for _ in range(3):
            responses.add(responses.GET, URL, json={"ok": 1}, status=200)
        session = new_session()
        start = time.monotonic()
        for _ in range(3):
            get(session, URL)
        elapsed = time.monotonic() - start
    finally:
        set_config(min_interval=0.0)

    assert elapsed >= 0.4  # two gaps between three calls
