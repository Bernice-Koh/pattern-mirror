"""Tests for structured JSON logging output."""

import json

import pytest
import structlog

from pattern_mirror.core.logging import configure_logging


def test_log_line_is_json_with_correlation_id(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(correlation_id="corr-123")

    structlog.get_logger("test").info("something_happened", detail="value")

    line = capsys.readouterr().out.strip().splitlines()[-1]
    record = json.loads(line)

    assert record["correlation_id"] == "corr-123"
    assert record["event"] == "something_happened"
    assert record["detail"] == "value"
    assert record["level"] == "info"
