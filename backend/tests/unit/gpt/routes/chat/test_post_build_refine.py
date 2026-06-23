"""Unit tests for routes.chat.post_build_refine.post_build_refine."""
import pytest
from fastapi import HTTPException

from api.pydantic_schemas.user.ai_task import PostBuildRefineRequest
from api.user.gpt.routes.chat import post_build_refine as mod
from api.user.gpt.routes.chat.post_build_refine import post_build_refine
from api.user.gpt.services.ai_file_helpers import upsert_ai_file
from models.task.session import PipelineStage


@pytest.mark.asyncio
async def test_post_build_refine_happy(db, user, task_session, monkeypatch):
    task_session.stage = PipelineStage.DONE
    await db.commit()
    await upsert_ai_file(db, task_session.id, "checker", "code")
    await db.commit()

    captured = {}

    async def fake_execute(db_, session, message, resolved):
        captured["resolved"] = resolved
        return {"updated_files": ["checker"], "response": "done",
                "statement": None, "technical_data": {}, "synced": True}

    monkeypatch.setattr(mod.modify_executor, "execute", fake_execute)

    req = PostBuildRefineRequest(session_id=task_session.id, message="tweak it")
    res = await post_build_refine(req, user_id=user.id, db=db)
    assert res["updated_files"] == ["checker"]
    assert res["technical_data"] == {"checker": "code"}
    assert captured["resolved"].scope == "task"


@pytest.mark.asyncio
async def test_post_build_refine_wrong_stage_400(db, user, task_session):
    task_session.stage = PipelineStage.STATEMENT
    await db.commit()
    req = PostBuildRefineRequest(session_id=task_session.id, message="x")
    with pytest.raises(HTTPException) as exc:
        await post_build_refine(req, user_id=user.id, db=db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_post_build_refine_no_files_400(db, user, task_session):
    task_session.stage = PipelineStage.DONE
    await db.commit()
    req = PostBuildRefineRequest(session_id=task_session.id, message="x")
    with pytest.raises(HTTPException) as exc:
        await post_build_refine(req, user_id=user.id, db=db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_post_build_refine_404(db, user):
    req = PostBuildRefineRequest(session_id="nope", message="x")
    with pytest.raises(HTTPException) as exc:
        await post_build_refine(req, user_id=user.id, db=db)
    assert exc.value.status_code == 404
