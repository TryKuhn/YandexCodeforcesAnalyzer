"""Unit tests for routes.sessions.get.get_session and chat_log reconstruction."""
import pytest
from fastapi import HTTPException

from api.user.gpt.routes.sessions.get import (get_session,
                                              _reconstruct_chat_log_from_history)


@pytest.mark.asyncio
async def test_get_session_happy_path(db, user, task_session):
    res = await get_session(task_session.id, user_id=user.id, db=db)
    assert res["session_id"] == task_session.id
    assert res["stage"] == task_session.stage
    assert res["technical_data"] == {}
    assert res["problem_settings"] == {}
    assert res["polygon_problem_id"] == 555


@pytest.mark.asyncio
async def test_get_session_reconstructs_chat_log_from_history(db, user, task_session):
    task_session.history = [
        {"role": "system", "content": "ignored"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": '{"name": "MyProblem"}'},
    ]
    task_session.chat_log = []
    await db.commit()

    res = await get_session(task_session.id, user_id=user.id, db=db)
    log = res["chat_log"]
    # system entry skipped
    assert all(e["role"] != "system" for e in log)
    assert log[0]["content"] == "hi"
    assert "MyProblem" in log[1]["content"]


@pytest.mark.asyncio
async def test_get_session_404(db, user):
    with pytest.raises(HTTPException) as exc:
        await get_session("missing", user_id=user.id, db=db)
    assert exc.value.status_code == 404


def test_reconstruct_handles_bad_json():
    out = _reconstruct_chat_log_from_history(
        [{"role": "assistant", "content": "{not json"}]
    )
    assert out[0]["content"] == "{not json"
