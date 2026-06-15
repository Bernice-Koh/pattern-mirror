"""Structured JSON logging via structlog, unified with the stdlib logger.

The correlation ID bound per request (see :mod:`pattern_mirror.core.middleware`)
lives in structlog's context-local storage, so the ``merge_contextvars``
processor stamps it onto every log line emitted during that request without any
call having to thread the ID through by hand. ``uvicorn``'s own loggers are
routed through the same renderer so framework and application lines are both
structured JSON.
"""

import logging
import sys

import structlog
from structlog.typing import Processor

_UVICORN_LOGGERS = ("uvicorn", "uvicorn.error", "uvicorn.access")


def configure_logging(log_level: str) -> None:
    """Configure structlog and the stdlib root logger to emit JSON to stdout.

    Args:
        log_level: A standard level name (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    level = logging.getLevelNamesMapping()[log_level]

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # Route uvicorn's own loggers through the root JSON handler instead of
    # letting them print their own unstructured lines.
    for name in _UVICORN_LOGGERS:
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True
