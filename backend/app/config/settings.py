"""Application configuration.

Defines the :class:`Settings` model used to load and validate environment
variables for the FastAPI application. Settings are cached with
``lru_cache`` so the environment is parsed only once per process.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings sourced from environment variables.

    Attributes:
        app_name: Human-readable name of the application.
        app_version: Current application version.
        environment: Deployment environment (e.g. ``development``,
            ``production``).
        debug: Whether the application is running in debug mode.
        host: Host interface the server binds to.
        port: Port the server listens on.
        api_prefix: Prefix applied to versioned business API routes.
        cors_origins: Comma-separated list of allowed CORS origins.
        groq_api_key: API key for the Groq LLM provider. ``None`` disables
            construction of the default provider.
        groq_model: Groq model identifier used for extraction completions.
        llm_timeout_seconds: Default timeout, in seconds, for LLM provider
            calls.
        db_host: MySQL server host.
        db_port: MySQL server port.
        db_user: MySQL username.
        db_password: MySQL password. Never hardcoded; sourced only from
            the environment.
        db_name: MySQL database (schema) name.
        database_url_override: A full SQLAlchemy database URL. When set,
            it takes precedence over the individual ``db_*`` fields.
            Intended for cases such as pointing at a test database.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="Pharmaceutical Complaint Management System")
    app_version: str = Field(default="1.0.0")
    environment: str = Field(default="development")
    debug: bool = Field(default=True)
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    api_prefix: str = Field(default="/api")
    cors_origins: str = Field(default="http://localhost:5173")
    groq_api_key: str | None = Field(default=None)
    groq_model: str = Field(default="llama-3.1-8b-instant")
    llm_timeout_seconds: float = Field(default=30.0)
    db_host: str = Field(default="localhost")
    db_port: int = Field(default=3306)
    db_user: str = Field(default="root")
    db_password: str = Field(default="")
    db_name: str = Field(default="pharma_complaints")
    database_url_override: str | None = Field(default=None, alias="DATABASE_URL")

    @property
    def cors_origin_list(self) -> list[str]:
        """Return ``cors_origins`` parsed into a list of origin strings.

        Returns:
            A list of trimmed, non-empty origin strings.
        """
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def database_url(self) -> str:
        """Return the SQLAlchemy database URL for the MySQL connection.

        Built entirely from environment-sourced settings; no credentials
        are hardcoded. When ``database_url_override`` (env var
        ``DATABASE_URL``) is set, it is returned as-is instead, which is
        useful for pointing the application at an alternate database
        (e.g. a test database) without overriding every component field.

        Returns:
            A SQLAlchemy-compatible database URL string.
        """
        if self.database_url_override:
            return self.database_url_override
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return a cached :class:`Settings` instance.

    Using ``lru_cache`` ensures the environment is read and validated only
    once, and the same instance is reused across the application.

    Returns:
        The cached application settings.
    """
    return Settings()
