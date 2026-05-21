import logging
import sys
from logging.handlers import RotatingFileHandler

import colorlog

from settings import settings

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
PLAIN_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
COLOR_FORMAT = "%(log_color)s%(asctime)s | %(levelname)-8s%(reset)s | %(cyan)s%(name)s%(reset)s | %(message)s"

LOG_DIR = settings.PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "app.log"
ERROR_LOG_FILE = LOG_DIR / "error.log"


def setup_logging(
    level: int = logging.INFO, log_to_file: bool = True, log_to_console: bool = True
) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    plain_formatter = logging.Formatter(PLAIN_FORMAT, DATE_FORMAT)

    if log_to_console:
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(level)
        console.setFormatter(
            colorlog.ColoredFormatter(
                COLOR_FORMAT,
                datefmt=DATE_FORMAT,
                log_colors={
                    "DEBUG": "cyan",
                    "INFO": "green",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "bold_red",
                },
            )
        )
        root_logger.addHandler(console)

    if log_to_file:
        file_handler = RotatingFileHandler(
            LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(plain_formatter)
        root_logger.addHandler(file_handler)

        error_handler = RotatingFileHandler(
            ERROR_LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(plain_formatter)
        root_logger.addHandler(error_handler)

    # Route uvicorn startup/error messages through our root handlers
    for name in ("uvicorn", "uvicorn.error"):
        uv_logger = logging.getLogger(name)
        uv_logger.handlers = []
        uv_logger.propagate = True

    # Disable uvicorn's built-in access log — HTTP requests are logged by LoggingMiddleware
    uv_access = logging.getLogger("uvicorn.access")
    uv_access.handlers = []
    uv_access.propagate = False


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
