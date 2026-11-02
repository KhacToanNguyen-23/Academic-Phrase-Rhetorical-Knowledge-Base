"""Structured logging; không log secrets hay manuscript raw (NFR-04, NFR-05).

Log lines carry identifiers, counts, and status codes only. Exception messages are not
logged because they can echo request input; ``safe_traceback`` keeps the stack frames.
"""

import logging
import traceback

from aprkb.core.config import settings

LOGGER_NAME = "aprkb"
_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


class _AprkbHandler(logging.StreamHandler):  # type: ignore[type-arg]
    """Marker type so repeated configuration does not add duplicate handlers."""


def configure_logging(level: str | None = None) -> None:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel((level or settings.log_level).upper())
    if not any(isinstance(handler, _AprkbHandler) for handler in logger.handlers):
        handler = _AprkbHandler()
        handler.setFormatter(logging.Formatter(_FORMAT))
        logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name if name.startswith(LOGGER_NAME) else f"{LOGGER_NAME}.{name}")


def safe_traceback(error: BaseException) -> str:
    """Return the exception type and stack frames without the exception message."""
    frames = "".join(traceback.format_tb(error.__traceback__))
    return f"{type(error).__name__}\n{frames}".rstrip()
