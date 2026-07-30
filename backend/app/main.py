"""FastAPI application entry point.

Creates and configures the FastAPI application instance: CORS middleware,
route registration, and startup/shutdown logging. Business logic is never
implemented here; this module only wires the application together.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.complaints import router as complaints_router
from app.api.health import router as health_router
from app.config.settings import get_settings
from app.schemas.complaint_response import ErrorResponse
from app.services.exceptions import (
    LLMServiceError,
    PDFCorruptedError,
    PDFEmptyError,
    PDFInvalidFileTypeError,
    SessionNotFoundError,
)
from app.utils.logger import configure_logging, get_logger

settings = get_settings()
configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Manage application startup and shutdown logging.

    Args:
        app: The FastAPI application instance.

    Yields:
        Control back to FastAPI while the application is running.
    """
    logger.info(
        "Starting %s v%s in '%s' environment",
        settings.app_name,
        settings.app_version,
        settings.environment,
    )
    yield
    logger.info("Shutting down %s", settings.app_name)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance.

    Returns:
        A fully configured :class:`FastAPI` application.
    """
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "AI-assisted intake of pharmaceutical customer complaints. "
            "The API assists Quality Assurance personnel; all business-"
            "critical decisions remain human-controlled."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(complaints_router)

    @app.exception_handler(SessionNotFoundError)
    async def session_not_found_handler(
        request: Request, exc: SessionNotFoundError
    ) -> JSONResponse:
        """Translate a missing session into a 404 error response.

        Args:
            request: The incoming request that triggered the error.
            exc: The raised exception.

        Returns:
            A JSON response following the standard error envelope.
        """
        return JSONResponse(
            status_code=404,
            content=ErrorResponse(
                message="Session not found.", errors=[str(exc)]
            ).model_dump(),
        )

    @app.exception_handler(LLMServiceError)
    async def llm_service_error_handler(
        request: Request, exc: LLMServiceError
    ) -> JSONResponse:
        """Translate an LLM Service failure into a 502 error response.

        Args:
            request: The incoming request that triggered the error.
            exc: The raised exception.

        Returns:
            A JSON response following the standard error envelope.
        """
        logger.error("LLM Service failure: %s", exc)
        return JSONResponse(
            status_code=502,
            content=ErrorResponse(
                message="The LLM service failed to process the request.",
                errors=[str(exc)],
            ).model_dump(),
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        """Translate an invalid request into a 400 error response.

        Args:
            request: The incoming request that triggered the error.
            exc: The raised exception.

        Returns:
            A JSON response following the standard error envelope.
        """
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(message="Invalid request.", errors=[str(exc)]).model_dump(),
        )

    @app.exception_handler(PDFInvalidFileTypeError)
    @app.exception_handler(PDFCorruptedError)
    @app.exception_handler(PDFEmptyError)
    async def pdf_error_handler(
        request: Request,
        exc: PDFInvalidFileTypeError | PDFCorruptedError | PDFEmptyError,
    ) -> JSONResponse:
        """Translate a PDF upload failure into a 400 error response.

        Args:
            request: The incoming request that triggered the error.
            exc: The raised exception.

        Returns:
            A JSON response following the standard error envelope.
        """
        logger.warning("PDF upload rejected: %s", exc)
        return JSONResponse(
            status_code=400,
            content=ErrorResponse(
                message="The uploaded PDF could not be processed.", errors=[str(exc)]
            ).model_dump(),
        )

    @app.get("/", tags=["Root"], summary="Root")
    def read_root() -> dict[str, str]:
        """Return basic application metadata at the root path.

        Returns:
            A simple payload identifying the running application and its
            current status.
        """
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "status": "running",
        }

    return app


app = create_app()
