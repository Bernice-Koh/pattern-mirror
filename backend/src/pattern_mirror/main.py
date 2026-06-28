"""FastAPI application factory.

``create_app`` builds a fully wired application. It is launched with uvicorn's
factory mode (``uvicorn pattern_mirror.main:create_app --factory``) so importing
this module has no side effects, while a missing variable still aborts boot
because uvicorn calls the factory at startup. Building via a factory also lets
tests construct the app against a controlled environment.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.requests import Request

from pattern_mirror import __version__
from pattern_mirror.api import analyze, health, interactions, streaming
from pattern_mirror.core.config import get_settings
from pattern_mirror.core.errors import (
    DocumentNotFoundError,
    FlagNotFoundError,
    PatternMirrorError,
)
from pattern_mirror.core.logging import configure_logging
from pattern_mirror.core.middleware import CorrelationIdMiddleware

_log = structlog.get_logger("pattern_mirror.app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Log service start/stop around the application's serving lifetime."""
    _log.info("service.start", version=__version__)
    yield
    _log.info("service.stop")


async def _handle_domain_error(request: Request, exc: Exception) -> JSONResponse:
    # Typed at Exception to match Starlette's handler signature, though it is
    # registered for PatternMirrorError only. Centralising the mapping here is
    # what keeps route handlers free of try/except.
    _log.error("unhandled_domain_error", error_type=type(exc).__name__, detail=str(exc))
    return JSONResponse(
        status_code=500,
        content={"error": type(exc).__name__, "detail": str(exc)},
    )


def _handle_not_found(request: Request, exc: Exception) -> JSONResponse:
    # A more specific handler than _handle_domain_error: a missing/foreign document or flag is
    # a client addressing error (404), not a server fault.
    return JSONResponse(
        status_code=404,
        content={"error": type(exc).__name__, "detail": str(exc)},
    )


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Loading settings here means a missing or invalid variable aborts startup
    (the importing process fails) rather than surfacing on the first request.
    """
    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(
        title="pattern-mirror",
        version=__version__,
        summary="Longitudinal bias-pattern analysis service.",
        lifespan=lifespan,
        debug=settings.app_env == "development",
    )
    app.add_middleware(CorrelationIdMiddleware)
    app.add_exception_handler(DocumentNotFoundError, _handle_not_found)
    app.add_exception_handler(FlagNotFoundError, _handle_not_found)
    app.add_exception_handler(PatternMirrorError, _handle_domain_error)
    app.include_router(health.router)
    app.include_router(analyze.router)
    app.include_router(streaming.router)
    app.include_router(interactions.router)
    return app
