"""Unit tests for api/user/polygon/problems/statement.py route handlers."""
import pytest

import api.user.polygon.problems.statement as mod
from api.pydantic_schemas.user.polygon_task import SaveStatementRequest
from api.user.polygon.problems.statement import (
    route_get_statement_resources,
    route_get_statements,
    route_save_statement,
)
from models.task.problem import PolygonProblem
from models.task.statement import PolygonStatement


async def _seed_problem(db, user, polygon_id=555):
    p = PolygonProblem(user_id=user.id, polygon_id=polygon_id, owner="o", name="n")
    db.add(p)
    await db.commit()
    await db.refresh(p)
    return p


@pytest.mark.asyncio
async def test_route_get_statements_from_cache(db, user):
    p = await _seed_problem(db, user)
    db.add(PolygonStatement(
        problem_id=p.id, lang="russian", encoding="utf-8",
        name="Имя", legend="Условие", input="Ввод", output="Вывод",
    ))
    await db.commit()

    result = await route_get_statements(polygon_id=555, user_id=user.id, db=db)
    assert "russian" in result
    assert result["russian"]["name"] == "Имя"
    assert result["russian"]["legend"] == "Условие"


@pytest.mark.asyncio
async def test_route_get_statements_falls_back_no_problem(monkeypatch, db, user):
    async def fake_get_statements(problem_id, user_id, db):
        return {"english": {"name": "fetched"}}

    monkeypatch.setattr(mod, "get_statements", fake_get_statements)
    result = await route_get_statements(polygon_id=12345, user_id=user.id, db=db)
    assert result == {"english": {"name": "fetched"}}


@pytest.mark.asyncio
async def test_route_get_statements_falls_back_no_cached_statements(monkeypatch, db, user):
    await _seed_problem(db, user)

    async def fake_get_statements(problem_id, user_id, db):
        return {"english": {"name": "live"}}

    monkeypatch.setattr(mod, "get_statements", fake_get_statements)
    result = await route_get_statements(polygon_id=555, user_id=user.id, db=db)
    assert result == {"english": {"name": "live"}}


@pytest.mark.asyncio
async def test_route_save_statement(monkeypatch, db, user):
    captured = {}

    async def fake_save_statement(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(mod, "save_statement", fake_save_statement)
    body = SaveStatementRequest(
        lang="russian", name="Заголовок", legend="L", input="I", output="O",
    )
    result = await route_save_statement(polygon_id=555, body=body, user_id=user.id, db=db)
    assert result == {"ok": True}
    assert captured["lang"] == "russian"
    assert captured["name"] == "Заголовок"
    assert captured["input_legend"] == "I"
    assert captured["output_legend"] == "O"


@pytest.mark.asyncio
async def test_route_get_statement_resources(monkeypatch, db, user):
    async def fake_get_statement_resources(problem_id, user_id, db):
        return [{"name": "img.png"}]

    monkeypatch.setattr(mod, "get_statement_resources", fake_get_statement_resources)
    result = await route_get_statement_resources(polygon_id=555, user_id=user.id, db=db)
    assert result == [{"name": "img.png"}]
