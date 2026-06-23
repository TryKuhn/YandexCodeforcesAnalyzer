"""Cache-upsert branch tests for api/user/polygon/statement/get/setatement.py."""
import pytest
from sqlalchemy import select

import api.user.polygon.statement.get.setatement as mod
from api.user.polygon.statement.get.setatement import get_statements
from models.task.problem import PolygonProblem
from models.task.statement import PolygonStatement


def _patch(monkeypatch, user, ret):
    async def fake_get_user(user_id, db):
        return user

    async def fake_polygon_call(method_name, params, u):
        return ret

    monkeypatch.setattr(mod, "get_user", fake_get_user)
    monkeypatch.setattr(mod, "polygon_call", fake_polygon_call)


@pytest.mark.asyncio
async def test_get_statements_inserts_and_updates(monkeypatch, db, user):
    p = PolygonProblem(user_id=user.id, polygon_id=42, owner="o", name="n")
    db.add(p)
    await db.commit()
    await db.refresh(p)
    db.add(PolygonStatement(
        problem_id=p.id, lang="russian", encoding="utf-8", name="Old"
    ))
    await db.commit()

    data = {
        "russian": {"encoding": "utf-8", "name": "Новое", "legend": "Условие"},
        "english": {"encoding": "utf-8", "name": "English", "legend": "Legend"},
    }
    _patch(monkeypatch, user, data)
    result = await get_statements(42, user.id, db)
    assert result == data

    rows = (
        await db.execute(select(PolygonStatement).filter_by(problem_id=p.id))
    ).scalars().all()
    by_lang = {r.lang: r for r in rows}
    assert by_lang["russian"].name == "Новое"
    assert by_lang["russian"].legend == "Условие"
    assert by_lang["english"].name == "English"


@pytest.mark.asyncio
async def test_get_statements_dict_no_cached_problem(monkeypatch, db, user):
    data = {"russian": {"name": "x"}}
    _patch(monkeypatch, user, data)
    result = await get_statements(9999, user.id, db)
    assert result == data
    rows = (await db.execute(select(PolygonStatement))).scalars().all()
    assert rows == []
