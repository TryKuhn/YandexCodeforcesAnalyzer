"""Unit tests for routes.sessions.update_problem_settings.update_problem_settings."""
import pytest
from fastapi import HTTPException

from api.pydantic_schemas.user.ai_task import (ProblemSettings,
                                               UpdateProblemSettingsRequest)
from api.user.gpt.routes.sessions.update_problem_settings import \
    update_problem_settings


@pytest.mark.asyncio
async def test_update_merges_settings(db, user, task_session):
    task_session.problem_settings = {"time_limit": 1000, "keep": "me"}
    await db.commit()

    req = UpdateProblemSettingsRequest(
        settings=ProblemSettings(time_limit=3000, memory_limit=512)
    )
    res = await update_problem_settings(
        task_session.id, req, user_id=user.id, db=db
    )
    ps = res["problem_settings"]
    assert ps["time_limit"] == 3000
    assert ps["memory_limit"] == 512
    # untouched key preserved
    assert ps["keep"] == "me"


@pytest.mark.asyncio
async def test_update_problem_settings_404(db, user):
    req = UpdateProblemSettingsRequest(settings=ProblemSettings())
    with pytest.raises(HTTPException) as exc:
        await update_problem_settings("nope", req, user_id=user.id, db=db)
    assert exc.value.status_code == 404
