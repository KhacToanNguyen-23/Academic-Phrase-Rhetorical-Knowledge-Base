from datetime import UTC, datetime, timedelta
from email.utils import format_datetime

import httpx
import pytest
from pydantic import ValidationError

from aprkb.core.config import Settings
from aprkb.worker.retry import classify_failure, retry_after_seconds, retry_delay


@pytest.mark.parametrize(
    "status,retry",
    [
        (408, True),
        (429, True),
        (500, True),
        (502, True),
        (503, True),
        (504, True),
        (400, False),
        (401, False),
        (403, False),
        (404, False),
        (422, False),
        (501, False),
    ],
)
def test_http_retry_classification(status, retry):
    response = httpx.Response(
        status,
        headers={"Retry-After": "30"},
        request=httpx.Request("GET", "https://example.invalid"),
    )
    error = httpx.HTTPStatusError("redacted", request=response.request, response=response)
    result = classify_failure(error)
    assert result.retryable is retry
    assert result.retry_after == (30 if retry else 0)


@pytest.mark.parametrize(
    "error,retry",
    [
        (ConnectionError("secret"), True),
        (TimeoutError(), True),
        (httpx.ConnectError("secret"), True),
        (PermissionError(), False),
        (ValueError(), False),
        (NotImplementedError(), False),
        (RuntimeError(), False),
        (httpx.UnsupportedProtocol("bad URL"), False),
        (httpx.LocalProtocolError("bad headers"), False),
    ],
)
def test_unknown_and_permanent_errors_fail_closed(error, retry):
    assert classify_failure(error).retryable is retry
    assert "secret" not in classify_failure(error).code


def test_retry_after_dates_invalid_values_and_jitter_bounds():
    now = datetime(2026, 11, 5, tzinfo=UTC)
    assert retry_after_seconds(format_datetime(now + timedelta(seconds=70)), now=now) == 70
    for value in (None, "bad", "-1", "nan", "inf"):
        assert retry_after_seconds(value, now=now) == 0
    for attempt in range(1, 15):
        ceiling = min(300, 10 * 2 ** (attempt - 1))
        assert ceiling / 2 <= retry_delay(attempt, base=10, cap=300) <= ceiling
    assert retry_delay(1, base=10, cap=300, retry_after=900) == 900


def test_invalid_worker_timing_is_rejected():
    with pytest.raises(ValidationError, match="half"):
        Settings(job_heartbeat_seconds=20, job_lease_seconds=30)
    with pytest.raises(ValidationError):
        Settings(job_retry_base_seconds=0)


def test_unrepresentable_retry_after_fails_without_overflow():
    response = httpx.Response(
        429,
        headers={"Retry-After": "1e300"},
        request=httpx.Request("GET", "https://example.invalid"),
    )
    error = httpx.HTTPStatusError("redacted", request=response.request, response=response)
    result = classify_failure(error)
    assert not result.retryable and result.code == "retry_after_out_of_range"
