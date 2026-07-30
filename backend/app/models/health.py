"""Data models for the health check endpoint."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Response payload returned by the health check endpoint.

    Attributes:
        status: Literal health status of the service.
        app_name: Name of the running application.
        version: Current application version.
        environment: Deployment environment the application is running in.
    """

    status: str = Field(default="ok")
    app_name: str
    version: str
    environment: str
