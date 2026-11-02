import logging

from aprkb.core.logging import LOGGER_NAME, configure_logging, get_logger, safe_traceback


def test_configure_logging_is_idempotent_and_sets_level() -> None:
    configure_logging("debug")
    configure_logging("info")

    logger = logging.getLogger(LOGGER_NAME)
    assert logger.level == logging.INFO
    assert sum(type(h).__name__ == "_AprkbHandler" for h in logger.handlers) == 1


def test_get_logger_nests_under_package_logger() -> None:
    assert get_logger("api").name == "aprkb.api"
    assert get_logger("aprkb.worker.runner").name == "aprkb.worker.runner"


def test_safe_traceback_keeps_frames_but_drops_message() -> None:
    runtime_value = "secret manuscript sentence"
    try:
        raise ValueError(runtime_value)
    except ValueError as error:
        text = safe_traceback(error)

    assert text.startswith("ValueError")
    assert "test_safe_traceback_keeps_frames_but_drops_message" in text
    assert "secret manuscript sentence" not in text
