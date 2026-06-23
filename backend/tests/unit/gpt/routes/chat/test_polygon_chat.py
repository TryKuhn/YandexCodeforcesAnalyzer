"""Unit tests for routes.chat.polygon_chat.polygon_agent_chat."""
import pytest
from fastapi import HTTPException

from api.user.gpt.routes.chat import polygon_chat as mod
from api.user.gpt.routes.chat.polygon_chat import (PolygonAgentChatRequest,
                                                   polygon_agent_chat)


@pytest.mark.asyncio
async def test_polygon_chat_happy(db, user, task_session, monkeypatch):
    captured = {}

    async def fake_agent(db_, session, uid, message, model, attachments):
        captured.update(message=message, model=model, attachments=attachments)
        return "agent says hi"

    monkeypatch.setattr(mod, "run_agent", fake_agent)
    monkeypatch.setattr(mod, "normalize_model", lambda m: f"norm:{m}")

    req = PolygonAgentChatRequest(
        session_id=task_session.id, message="inspect", attachments=[{"type": "t"}]
    )
    res = await polygon_agent_chat(req, user_id=user.id, db=db)
    assert res == {"response": "agent says hi"}
    assert captured["message"] == "inspect"
    assert captured["model"].startswith("norm:")
    assert captured["attachments"] == [{"type": "t"}]


@pytest.mark.asyncio
async def test_polygon_chat_no_polygon_id_404(db, user, task_session, monkeypatch):
    task_session.polygon_problem_id = None
    await db.commit()
    monkeypatch.setattr(mod, "run_agent", None)
    monkeypatch.setattr(mod, "normalize_model", lambda m: m)

    req = PolygonAgentChatRequest(session_id=task_session.id, message="x")
    with pytest.raises(HTTPException) as exc:
        await polygon_agent_chat(req, user_id=user.id, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_polygon_chat_session_404(db, user, monkeypatch):
    monkeypatch.setattr(mod, "run_agent", None)
    monkeypatch.setattr(mod, "normalize_model", lambda m: m)
    req = PolygonAgentChatRequest(session_id="nope", message="x")
    with pytest.raises(HTTPException) as exc:
        await polygon_agent_chat(req, user_id=user.id, db=db)
    assert exc.value.status_code == 404
