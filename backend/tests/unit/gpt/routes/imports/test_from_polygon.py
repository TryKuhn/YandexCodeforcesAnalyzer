"""Unit tests for routes.imports.from_polygon.import_from_polygon."""
import pytest
from sqlalchemy import select

from api.pydantic_schemas.user.ai_task import ImportFromPolygonRequest
from api.user.gpt.routes.imports import from_polygon as mod
from api.user.gpt.routes.imports.from_polygon import (import_from_polygon,
                                                      _extract_statement)
from models.task.session import PipelineStage, TaskSession


@pytest.mark.asyncio
async def test_import_from_polygon_creates_session(db, user, monkeypatch):
    async def fake_get_statements(problem_id, uid, db_):
        return {"russian": {"name": "Имя", "legend": "Лег", "input": "in",
                            "output": "out", "notes": "n", "tutorial": "t"}}

    monkeypatch.setattr(mod, "get_statements", fake_get_statements)
    monkeypatch.setattr(mod, "normalize_model", lambda m: m)

    req = ImportFromPolygonRequest(polygon_problem_id=42, model="m")
    res = await import_from_polygon(req, user_id=user.id, db=db)
    assert res["statement"]["name"] == "Имя"
    assert res["polygon_problem_id"] == 42
    assert res["stage"] == PipelineStage.STATEMENT

    saved = (await db.execute(select(TaskSession))).scalars().one()
    assert saved.polygon_problem_id == 42
    assert saved.statement["legend"] == "Лег"


def test_extract_statement_falls_back_to_english():
    raw = {"english": {"name": "Name", "legend": "L"}}
    out = _extract_statement(raw)
    assert out["name"] == "Name"
    assert out["notes"] == ""


def test_extract_statement_empty_for_non_dict():
    out = _extract_statement([])
    assert out["name"] == ""
    assert out["legend"] == ""
