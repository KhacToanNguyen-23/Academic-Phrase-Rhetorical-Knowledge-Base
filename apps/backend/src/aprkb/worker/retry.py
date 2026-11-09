"""Conservative, redacted failure classification and bounded retry scheduling."""

import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx
from sqlalchemy.exc import DBAPIError


@dataclass(frozen=True)
class Failure:
    code: str
    retryable: bool
    retry_after: float = 0


def retry_after_seconds(value: str | None, *, now: datetime | None = None) -> float:
    if not value:
        return 0
    try:
        seconds = float(value)
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
            if date.tzinfo is None:
                date = date.replace(tzinfo=UTC)
            seconds = (date - (now or datetime.now(UTC))).total_seconds()
        except (TypeError, ValueError, OverflowError):
            return 0
    return max(0, seconds) if math.isfinite(seconds) else 0


def classify_failure(error: Exception) -> Failure:
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        retryable = status in {408, 429, 500, 502, 503, 504}
        delay = retry_after_seconds(error.response.headers.get("Retry-After")) if retryable else 0
        if delay >= (datetime.max.replace(tzinfo=UTC) - datetime.now(UTC)).total_seconds() - 1:
            return Failure("retry_after_out_of_range", False)
        return Failure(
            f"http_{status}",
            retryable,
            delay,
        )
    if isinstance(
        error,
        (
            httpx.NetworkError,
            httpx.TimeoutException,
            httpx.RemoteProtocolError,
            ConnectionError,
            TimeoutError,
        ),
    ):
        return Failure("transport_unavailable", True)
    if isinstance(error, DBAPIError):
        code = getattr(error.orig, "sqlstate", None) or getattr(error.orig, "pgcode", None)
        return Failure(
            "database_transient",
            bool(
                error.connection_invalidated
                or code
                in {
                    "40001",
                    "40P01",
                    "53300",
                    "57P01",
                    "57P02",
                    "57P03",
                    "08000",
                    "08003",
                    "08006",
                }
            ),
        )
    if isinstance(error, PermissionError):
        return Failure("permission_denied", False)
    if isinstance(error, NotImplementedError):
        return Failure("unsupported_operation", False)
    if isinstance(error, (ValueError, TypeError, FileNotFoundError)):
        return Failure("invalid_input", False)
    return Failure("unexpected_error", False)


def retry_delay(attempt: int, *, base: float, cap: float, retry_after: float = 0) -> float:
    # Equal jitter avoids a zero-delay hot loop. Retry-After is a minimum, not capped.
    ceiling = min(cap, base * 2 ** min(max(attempt - 1, 0), 30))
    return max(retry_after, random.uniform(ceiling / 2, ceiling))
