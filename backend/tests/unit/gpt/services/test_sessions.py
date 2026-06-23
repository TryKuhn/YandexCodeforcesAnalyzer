"""Unit tests for the TaskSession helper layer (services.sessions)."""
import pytest
from fastapi import HTTPException

from api.user.gpt.services import sessions as S
from models.task.session import ProblemType


def test_chat_message_shape():
    msg = S.chat_message("user", "hi", context={"scope": "task"})
    assert msg["role"] == "user" and msg["content"] == "hi"
    assert msg["context"] == {"scope": "task"}
    assert msg["id"] and msg["timestamp"]


def test_new_id_unique():
    assert S.new_id() != S.new_id()


def test_now_helpers():
    assert S.now_utc().tzinfo is None
    assert "T" in S.now_iso()


def test_is_interactive(task_session):
    assert S.is_interactive(task_session) is False
    task_session.problem_type = ProblemType.INTERACTIVE
    assert S.is_interactive(task_session) is True


@pytest.mark.asyncio
async def test_get_session_or_404_found(db, task_session):
    got = await S.get_session_or_404(db, task_session.id)
    assert got.id == task_session.id


@pytest.mark.asyncio
async def test_get_session_or_404_missing(db):
    with pytest.raises(HTTPException) as e:
        await S.get_session_or_404(db, "nope")
    assert e.value.status_code == 404


@pytest.mark.asyncio
async def test_get_session_or_404_wrong_owner(db, task_session):
    with pytest.raises(HTTPException) as e:
        await S.get_session_or_404(db, task_session.id, user_id=999)
    assert e.value.status_code == 403


@pytest.mark.asyncio
async def test_update_session_patches_columns(db, task_session):
    await S.update_session(db, task_session.id, {"model": "new-model"})
    refreshed = await S.get_session_or_404(db, task_session.id)
    assert refreshed.model == "new-model"


@pytest.mark.asyncio
async def test_append_chat_log_accumulates(db, task_session):
    await S.append_chat_log(db, task_session.id, [S.chat_message("user", "a")])
    await S.append_chat_log(db, task_session.id, [S.chat_message("assistant", "b")])
    refreshed = await S.get_session_or_404(db, task_session.id)
    assert [m["content"] for m in refreshed.chat_log] == ["a", "b"]


@pytest.mark.asyncio
async def test_append_chat_log_missing_session_is_noop(db):
    await S.append_chat_log(db, "ghost", [S.chat_message("user", "x")])
