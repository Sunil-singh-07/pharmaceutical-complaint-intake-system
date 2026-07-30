"""Logging configuration for the application.

Provides a single :func:`configure_logging` entry point so logging is
configured consistently, and a :func:`get_logger` helper for modules to
obtain a named logger.
"""

import logging
import sys

from app.config.settings import get_settings


def configure_logging() -> None:
    """Configure the root logger for the application.

    Sets the log level based on the ``debug`` setting and installs a single
    stream handler with a consistent formatter. Safe to call multiple
    times; existing handlers are cleared before reconfiguration.
    """
    settings = get_settings()
    log_level = logging.DEBUG if settings.debug else logging.INFO

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()

    handler = logging.StreamHandler(stream=sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger.

    Args:
        name: Name of the logger, typically ``__name__`` of the caller.

    Returns:
        A configured :class:`logging.Logger` instance.
    """
    return logging.getLogger(name)
