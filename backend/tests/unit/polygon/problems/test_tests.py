"""Unit tests for api/user/polygon/problems/tests.py route handlers."""
import pytest

import api.user.polygon.problems.tests as mod
from api.pydantic_schemas.user.polygon_task import UpdateTestRequest
from api.user.polygon.problems.tests import (
    route_get_test_answer,
    route_get_test_input,
    route_get_tests,
    route_save_test,
)


@pytest.mark.asyncio
async def test_route_get_tests(monkeypatch, db, user):
    captured = {}

    async def fake_get_tests(**kwargs):
        captured.update(kwargs)
        return [{"index": 1}]

    monkeypatch.setattr(mod, "get_tests", fake_get_tests)
    result = await route_get_tests(
        polygon_id=555, testset="tests", no_inputs=True, user_id=user.id, db=db
    )
    assert result == [{"index": 1}]
    assert captured["no_inputs"] is True
    assert captured["testset"] == "tests"


@pytest.mark.asyncio
async def test_route_get_test_input(monkeypatch, db, user):
    async def fake_get_test_input(**kwargs):
        return "1 2 3"

    monkeypatch.setattr(mod, "get_test_input", fake_get_test_input)
    result = await route_get_test_input(
        polygon_id=555, testset="tests", index=1, user_id=user.id, db=db
    )
    assert result == {"content": "1 2 3"}


@pytest.mark.asyncio
async def test_route_get_test_answer(monkeypatch, db, user):
    async def fake_get_test_answer(**kwargs):
        return "6"

    monkeypatch.setattr(mod, "get_test_answer", fake_get_test_answer)
    result = await route_get_test_answer(
        polygon_id=555, testset="tests", index=1, user_id=user.id, db=db
    )
    assert result == {"content": "6"}


@pytest.mark.asyncio
async def test_route_save_test_passes_str_input(monkeypatch, db, user):
    captured = {}

    async def fake_save_test(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(mod, "save_test", fake_save_test)
    body = UpdateTestRequest(test_input="привет")
    result = await route_save_test(
        polygon_id=555, testset="tests", index=2, body=body, user_id=user.id, db=db
    )
    assert result == {"ok": True}
    # passed as str so saveTest includes it in the signed params (not bytes)
    assert captured["test_input"] == "привет"
    assert captured["test_index"] == 2
    assert captured["check_existing"] is False
