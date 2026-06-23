"""Unit tests for routes.sessions.sync_from_polygon.sync_from_polygon."""
import pytest
from fastapi import HTTPException

from api.user.gpt.routes.sessions import sync_from_polygon as mod
from api.user.gpt.routes.sessions.sync_from_polygon import sync_from_polygon


@pytest.mark.asyncio
async def test_sync_happy_path(db, user, task_session, monkeypatch):
    async def fake_reload(db_, session):
        return {"reloaded": ["checker"], "statement": True}

    monkeypatch.setattr(mod, "reload_from_polygon", fake_reload)

    res = await sync_from_polygon(task_session.id, user_id=user.id, db=db)
    assert res["session_id"] == task_session.id
    assert res["reloaded"] == ["checker"]
    assert res["statement"] is True


@pytest.mark.asyncio
async def test_sync_missing_session_404(db, user, monkeypatch):
    monkeypatch.setattr(mod, "reload_from_polygon", lambda *a, **k: None)
    with pytest.raises(HTTPException) as exc:
        await sync_from_polygon("nope", user_id=user.id, db=db)
    assert exc.value.status_code == 404
