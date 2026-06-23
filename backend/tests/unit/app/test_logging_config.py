"""Unit tests for app/logging_config.py — logging setup helpers."""
import logging

from app.logging_config import get_logger, setup_logging


def test_get_logger_returns_named_logger():
    logger = get_logger("my.module")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "my.module"


def test_setup_logging_console_only_adds_one_handler():
    root = logging.getLogger()
    original = root.handlers[:]
    original_level = root.level
    try:
        setup_logging(level=logging.DEBUG, log_to_file=False, log_to_console=True)
        assert root.level == logging.DEBUG
        assert len(root.handlers) == 1  # only console handler
        # uvicorn.access logging is silenced / non-propagating
        uv_access = logging.getLogger("uvicorn.access")
        assert uv_access.propagate is False
    finally:
        # Restore root logger handlers to avoid leaking state into other tests.
        for h in root.handlers[:]:
            root.removeHandler(h)
        for h in original:
            root.addHandler(h)
        root.setLevel(original_level)


def test_setup_logging_no_handlers_when_all_disabled():
    root = logging.getLogger()
    original = root.handlers[:]
    original_level = root.level
    try:
        setup_logging(log_to_file=False, log_to_console=False)
        assert root.handlers == []
    finally:
        for h in root.handlers[:]:
            root.removeHandler(h)
        for h in original:
            root.addHandler(h)
        root.setLevel(original_level)
