"""Health check API route.

Exposes a lightweight endpoint used to verify that the application has
started successfully. Intended for local checks, container orchestration
probes, and load balancer health checks.
"""

from fastapi import APIRouter

from app.config.settings import get_settings
from app.models.health import HealthResponse

router = APIRouter(prefix="/api", tags=["Health"])


@router.get("/health", response_model=HealthResponse, summary="Health check")
def get_health() -> HealthResponse:
    """Return the current health status of the application.

    Returns:
        A :class:`HealthResponse` indicating the service is running, along
        with basic application metadata.
    """
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app_name=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )
