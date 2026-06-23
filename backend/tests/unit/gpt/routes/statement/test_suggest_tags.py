"""Unit tests for routes.statement.suggest_tags.suggest_tags."""
import pytest
from fastapi import HTTPException

from api.pydantic_schemas.user.ai_task import SuggestTagsRequest
from api.user.gpt.routes.statement import suggest_tags as mod
from api.user.gpt.routes.statement.suggest_tags import suggest_tags


@pytest.mark.asyncio
async def test_suggest_tags_happy(db, user, task_session, monkeypatch):
    task_session.statement = {"name": "P"}
    await db.commit()

    async def fake_ensure(db_, session):
        return None

    async def fake_suggest(statement, model):
        return ["math", "greedy"]

    monkeypatch.setattr(mod, "ensure_files_loaded", fake_ensure)
    monkeypatch.setattr(mod.tags_gen, "suggest", fake_suggest)

    req = SuggestTagsRequest(session_id=task_session.id)
    res = await suggest_tags(req, user_id=user.id, db=db)
    assert res["suggested_tags"] == ["math", "greedy"]


@pytest.mark.asyncio
async def test_suggest_tags_no_statement_400(db, user, task_session, monkeypatch):
    async def fake_ensure(db_, session):
        return None

    monkeypatch.setattr(mod, "ensure_files_loaded", fake_ensure)
    req = SuggestTagsRequest(session_id=task_session.id)
    with pytest.raises(HTTPException) as exc:
        await suggest_tags(req, user_id=user.id, db=db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_suggest_tags_404(db, user, monkeypatch):
    monkeypatch.setattr(mod, "ensure_files_loaded", lambda *a, **k: None)
    req = SuggestTagsRequest(session_id="nope")
    with pytest.raises(HTTPException) as exc:
        await suggest_tags(req, user_id=user.id, db=db)
    assert exc.value.status_code == 404
