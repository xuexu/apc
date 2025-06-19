"""
Centralized logging configuration

In entrypoints (__main__.py, etc):
from apc.logging_config import setup_logging
setup_logging()

In other files (include 'level="DEBUG"' for testing):
from apc.logging_config import get_logger
logger = get_logger(__name__)
"""

import logging
from typing import Optional

from rich.logging import RichHandler


def setup_logging(level: str = "INFO") -> None:
    """
    Configure the root logger with a rich, colorized console handler.

    Args:
        level: Minimum log level for console output (e.g., "DEBUG", "INFO").
    """
    logging.basicConfig(
        level=level.upper(),
        format="%(module)s.%(funcName)s: %(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(markup=True, rich_tracebacks=True)],
    )


def get_logger(
    name: Optional[str] = None,
    level: Optional[str] = None,
) -> logging.Logger:
    """
    Get a logger by name, initializing logging if necessary.

    Args:
        name: Logger name, usually __name__. Defaults to root logger if None.
        level: If logging isn't already configured, use this level for setup.

    Returns:
        Logger object.
    """
    root = logging.getLogger()
    if not root.hasHandlers():
        setup_logging(level or "INFO")
    return logging.getLogger(name)
