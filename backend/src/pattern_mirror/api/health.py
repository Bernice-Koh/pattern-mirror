"""Healthcheck endpoint: a liveness signal for orchestrators and smoke tests."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from pattern_mirror import __version__
from pattern_mirror.core.config import Settings, get_settings

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Service health payload returned by the healthcheck."""

    status: Literal["ok"]
    app_env: str
    version: str


@router.get("/health", response_model=HealthResponse, summary="Liveness healthcheck")
def healthcheck(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    """Report that the service is up, with its running environment and version."""
    return HealthResponse(status="ok", app_env=settings.app_env, version=__version__)
