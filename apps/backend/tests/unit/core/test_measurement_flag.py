"""ADR-0015: a fresh checkout serves the Metric & Measurement catalog without extra config."""

import pytest

from aprkb.core.config import Settings


@pytest.mark.parametrize(
    ("env", "expected"),
    [(None, True), ("", True), ("  ", True), ("false", False), ("true", True)],
)
def test_measurement_flag_defaults_on(monkeypatch, env, expected):
    monkeypatch.delenv("MEASUREMENT_ENABLED", raising=False)
    if env is not None:
        monkeypatch.setenv("MEASUREMENT_ENABLED", env)
    assert Settings(_env_file=None).measurement_enabled is expected
