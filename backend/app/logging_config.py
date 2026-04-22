import logging
import sys
from logging.handlers import RotatingFileHandler

from settings import settings

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

LOG_DIR = settings.PROJECT_ROOT / 'logs'
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / 'app.log'
ERROR_LOG_FILE = LOG_DIR / 'error.log'


def setup_logging(level=logging.INFO, log_to_file=True, log_to_console=True):
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for handler in root_logger.handlers:
        root_logger.removeHandler(handler)

    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    logger = logging.getLogger(__name__)

    if log_to_console:
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(level)
        console.setFormatter(formatter)
        root_logger.addHandler(console)

        logger.info('Console logger configured!')

    if log_to_file:
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8',
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        logger.info(f'File logger configured! Main log file: {LOG_FILE}')

        error_file_handler = RotatingFileHandler(
            ERROR_LOG_FILE,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8',
        )

        error_file_handler.setLevel(logging.ERROR)
        error_file_handler.setFormatter(formatter)
        root_logger.addHandler(error_file_handler)

        logger.info(f'Error logger configured! Error log file: {ERROR_LOG_FILE}')


def get_logger(name: str):
    return logging.getLogger(name)
