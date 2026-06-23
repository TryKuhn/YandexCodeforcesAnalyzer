"""Unit tests for routes.files.refine_file.refine_file."""
import pytest
from fastapi import HTTPException

from api.pydantic_schemas.user.ai_task import RefineFileRequest
from api.user.gpt.routes.files import refine_file as mod
from api.user.gpt.routes.files.refine_file import refine_file
from api.user.gpt.services.ai_file_helpers import get_all_file_contents, upsert_ai_file


@pytest.mark.asyncio
async def test_refine_file_happy(db, user, task_session, monkeypatch):
    await upsert_ai_file(db, task_session.id, "checker", "old code")
    await db.commit()

    captured = {}

    async def fake_refine(file_type, current_code, feedback, statement, model, interactive):
        captured.update(
            file_type=file_type, current_code=current_code,
            feedback=feedback, interactive=interactive,
        )
        return "new code"

    monkeypatch.setattr(mod.file_gen, "refine", fake_refine)

    req = RefineFileRequest(
        session_id=task_session.id, file_key="checker", feedback="tidy"
    )
    res = await refine_file(req, user_id=user.id, db=db)
    assert captured["current_code"] == "old code"
    assert captured["feedback"] == "tidy"
    assert captured["interactive"] is False
    assert res["new_code"] == "new code"
    files = await get_all_file_contents(db, task_session.id)
    assert files["checker"] == "new code"


@pytest.mark.asyncio
async def test_refine_file_missing_file_400(db, user, task_session, monkeypatch):
    monkeypatch.setattr(mod.file_gen, "refine", None)
    req = RefineFileRequest(
        session_id=task_session.id, file_key="checker", feedback="x"
    )
    with pytest.raises(HTTPException) as exc:
        await refine_file(req, user_id=user.id, db=db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_refine_file_404(db, user):
    req = RefineFileRequest(session_id="nope", file_key="checker", feedback="x")
    with pytest.raises(HTTPException) as exc:
        await refine_file(req, user_id=user.id, db=db)
    assert exc.value.status_code == 404
