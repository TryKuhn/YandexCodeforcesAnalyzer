"""Unit tests for logs/logs.py — the log_middleware decorator."""
import logging

import pytest

from logs.logs import log_middleware


@pytest.mark.asyncio
async def test_log_middleware_passes_through_result(caplog):
    @log_middleware
    async def handler(a, b):
        return a + b

    with caplog.at_level(logging.INFO):
        result = await handler(2, 3)

    assert result == 5
    messages = [r.getMessage() for r in caplog.records]
    assert any("Started handler" in m for m in messages)
    assert any("Ended handler" in m for m in messages)


@pytest.mark.asyncio
async def test_log_middleware_logs_and_reraises_exception(caplog):
    @log_middleware
    async def boom():
        raise ValueError("kaboom")

    with caplog.at_level(logging.INFO):
        with pytest.raises(ValueError, match="kaboom"):
            await boom()

    messages = [r.getMessage() for r in caplog.records]
    assert any("Exception caught in boom" in m for m in messages)
    # finally-block still logs "Ended" even on failure.
    assert any("Ended boom" in m for m in messages)
