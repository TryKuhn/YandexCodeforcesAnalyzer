"""Unit tests for routes.sessions.update_settings.update_session_settings."""
import pytest
from fastapi import HTTPException

from api.pydantic_schemas.user.ai_task import UpdateSessionSettingsRequest
from api.user.gpt.routes.sessions import update_settings as mod
from api.user.gpt.routes.sessions.update_settings import update_session_settings


@pytest.mark.asyncio
async def test_update_model_and_prompt(db, user, task_session, monkeypatch):
    monkeypatch.setattr(mod, "normalize_model", lambda m: f"norm:{m}")

    req = UpdateSessionSettingsRequest(model="gpt", system_prompt="be terse")
    res = await update_session_settings(task_session.id, req, user_id=user.id, db=db)
    assert res["status"] == "ok"
    assert res["model"] == "norm:gpt"
    assert res["system_prompt"] == "be terse"


@pytest.mark.asyncio
async def test_update_partial_keeps_existing(db, user, task_session, monkeypatch):
    monkeypatch.setattr(mod, "normalize_model", lambda m: m)
    original_model = task_session.model

    req = UpdateSessionSettingsRequest(system_prompt="only prompt")
    res = await update_session_settings(task_session.id, req, user_id=user.id, db=db)
    assert res["model"] == original_model
    assert res["system_prompt"] == "only prompt"


@pytest.mark.asyncio
async def test_update_settings_404(db, user):
    req = UpdateSessionSettingsRequest(model="m")
    with pytest.raises(HTTPException) as exc:
        await update_session_settings("nope", req, user_id=user.id, db=db)
    assert exc.value.status_code == 404
