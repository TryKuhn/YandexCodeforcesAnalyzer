"""Unit tests for routes.imports.from_polygon_full.import_from_polygon_full."""
import pytest

from api.pydantic_schemas.user.ai_task import ImportFromPolygonFullRequest
from api.user.gpt.routes.imports import from_polygon_full as mod
from api.user.gpt.routes.imports.from_polygon_full import import_from_polygon_full


@pytest.mark.asyncio
async def test_import_full_delegates(db, user, monkeypatch):
    captured = {}

    async def fake_import_full(db_, uid, *, problem_id, model, load_files):
        captured.update(uid=uid, problem_id=problem_id, model=model,
                        load_files=load_files)
        return {"session_id": "new", "polygon_problem_id": problem_id}

    monkeypatch.setattr(mod, "import_full", fake_import_full)
    monkeypatch.setattr(mod, "normalize_model", lambda m: f"norm:{m}")

    req = ImportFromPolygonFullRequest(
        polygon_problem_id=7, model="gpt", load_files=True
    )
    res = await import_from_polygon_full(req, user_id=user.id, db=db)
    assert res == {"session_id": "new", "polygon_problem_id": 7}
    assert captured["uid"] == user.id
    assert captured["problem_id"] == 7
    assert captured["model"] == "norm:gpt"
    assert captured["load_files"] is True


@pytest.mark.asyncio
async def test_import_full_load_files_false(db, user, monkeypatch):
    captured = {}

    async def fake_import_full(db_, uid, *, problem_id, model, load_files):
        captured["load_files"] = load_files
        return {}

    monkeypatch.setattr(mod, "import_full", fake_import_full)
    monkeypatch.setattr(mod, "normalize_model", lambda m: m)

    req = ImportFromPolygonFullRequest(
        polygon_problem_id=1, model="m", load_files=False
    )
    await import_from_polygon_full(req, user_id=user.id, db=db)
    assert captured["load_files"] is False
