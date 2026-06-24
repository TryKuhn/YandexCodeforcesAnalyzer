"""Unit tests for routes.chat.chat.unified_chat (LLM intent dispatch)."""
import pytest
from fastapi import HTTPException

from api.pydantic_schemas.user.ai_task import ChatContext, ChatRequest, ChatResponse
from api.user.gpt.routes.chat import chat as mod
from api.user.gpt.routes.chat.chat import unified_chat
from api.user.gpt.services.sessions import get_session_or_404

MOD = "api.user.gpt.routes.chat.chat"


@pytest.fixture(autouse=True)
def _no_background(monkeypatch):
    """Track background build kick-offs without scheduling real work.

    We only intercept ``run_build_with_repair`` (the coroutine fed to
    ``asyncio.create_task``): it records the call and returns a trivially
    completing coroutine, so the created task is a harmless no-op. We do NOT
    patch ``asyncio.create_task`` itself — pytest-asyncio relies on it.
    """
    created = []

    async def fake_repair(sid):
        created.append(sid)

    monkeypatch.setattr(mod, "run_build_with_repair", fake_repair)

    async def fake_ensure(db_, session):
        return None

    monkeypatch.setattr(mod, "ensure_files_loaded", fake_ensure)
    return created


def _stub_intent(monkeypatch, action, file_key=None):
    async def fake_classify(message, hint, available_files, main_model=None):
        return {"action": action, "file_key": file_key}

    monkeypatch.setattr(mod.intent_router, "classify_action", fake_classify)


@pytest.mark.asyncio
async def test_chat_answer_action(db, user, task_session, monkeypatch):
    task_session.statement = {"name": "P"}
    await db.commit()
    _stub_intent(monkeypatch, "answer")

    async def fake_resolve(db_, session, ctx):
        return object()

    async def fake_answer(**kwargs):
        return "here is your answer"

    monkeypatch.setattr(mod.context_resolver, "resolve", fake_resolve)
    monkeypatch.setattr(mod.answer_executor, "execute", fake_answer)

    req = ChatRequest(session_id=task_session.id, message="what is this?")
    res = await unified_chat(req, user_id=user.id, db=db)
    assert isinstance(res, ChatResponse)
    assert res.action == "answer"
    assert res.response == "here is your answer"
    # user + assistant messages persisted
    s = await get_session_or_404(db, task_session.id)
    roles = [m["role"] for m in s.chat_log]
    assert roles == ["user", "assistant"]


@pytest.mark.asyncio
async def test_chat_answer_gets_history_from_chat_log(db, user, task_session, monkeypatch):
    """Regression: the answer model must see prior turns. They live in chat_log,
    not session.history, so history must be derived from chat_log."""
    task_session.chat_log = [
        {"role": "user", "content": "сделай задачу про qsort", "id": "1"},
        {"role": "assistant", "content": "вот разбор задачи", "id": "2", "action": "answer"},
    ]
    await db.commit()
    _stub_intent(monkeypatch, "answer")

    async def fake_resolve(db_, session, ctx):
        return object()

    captured = {}

    async def fake_answer(**kwargs):
        captured.update(kwargs)
        return "ok"

    monkeypatch.setattr(mod.context_resolver, "resolve", fake_resolve)
    monkeypatch.setattr(mod.answer_executor, "execute", fake_answer)

    req = ChatRequest(session_id=task_session.id, message="да всё верно")
    await unified_chat(req, user_id=user.id, db=db)

    # The two prior turns are forwarded as clean {role, content} dicts; the
    # current message is NOT in history (the executor adds it itself).
    assert captured["history"] == [
        {"role": "user", "content": "сделай задачу про qsort"},
        {"role": "assistant", "content": "вот разбор задачи"},
    ]


@pytest.mark.asyncio
async def test_chat_modify_edit_file(db, user, task_session, monkeypatch):
    _stub_intent(monkeypatch, "edit_file", file_key="checker")

    captured = {}

    async def fake_execute(db_, session, message, resolved):
        captured["resolved"] = resolved
        return {
            "response": "edited", "updated_files": ["checker"],
            "statement": None, "technical_data": {"checker": "new"},
            "synced": True, "build": False,
        }

    monkeypatch.setattr(mod.modify_executor, "execute", fake_execute)

    req = ChatRequest(
        session_id=task_session.id, message="fix checker",
        context=ChatContext(scope="file", file_key="checker"),
    )
    res = await unified_chat(req, user_id=user.id, db=db)
    assert res.action == "modify"
    assert res.updated_files == ["checker"]
    assert res.synced_to_polygon is True
    assert captured["resolved"].scope == "file"
    assert captured["resolved"].file_key == "checker"


@pytest.mark.asyncio
async def test_chat_regenerate_action(db, user, task_session, monkeypatch):
    _stub_intent(monkeypatch, "regenerate")

    called = {"regen": False}

    async def fake_regen(db_, session, message):
        called["regen"] = True
        return {
            "response": "regenerated", "updated_files": ["checker", "solution_cpp"],
            "statement": None, "technical_data": {}, "synced": False, "build": False,
        }

    monkeypatch.setattr(mod.modify_executor, "regenerate", fake_regen)

    req = ChatRequest(session_id=task_session.id, message="regenerate everything")
    res = await unified_chat(req, user_id=user.id, db=db)
    assert called["regen"] is True
    assert res.action == "modify"
    assert res.updated_files == ["checker", "solution_cpp"]


@pytest.mark.asyncio
async def test_chat_build_action_kicks_off_build(db, user, task_session, monkeypatch):
    _stub_intent(monkeypatch, "build")

    req = ChatRequest(session_id=task_session.id, message="build the package")
    res = await unified_chat(req, user_id=user.id, db=db)
    assert res.action == "answer"
    assert res.is_error is False
    # build branch taken: confirmation text references the package build
    assert "сборку" in res.response


@pytest.mark.asyncio
async def test_chat_build_action_no_polygon_id_errors(db, user, task_session, monkeypatch):
    task_session.polygon_problem_id = None
    await db.commit()
    _stub_intent(monkeypatch, "build")

    req = ChatRequest(session_id=task_session.id, message="build")
    res = await unified_chat(req, user_id=user.id, db=db)
    assert res.is_error is True


@pytest.mark.asyncio
async def test_chat_modify_with_build_flag_kicks_off(db, user, task_session, monkeypatch):
    _stub_intent(monkeypatch, "edit_task")

    async def fake_execute(db_, session, message, resolved):
        return {
            "response": "rebuilt task", "updated_files": ["checker"],
            "statement": None, "technical_data": {}, "synced": True, "build": True,
        }

    monkeypatch.setattr(mod.modify_executor, "execute", fake_execute)

    req = ChatRequest(session_id=task_session.id, message="rework the whole task")
    res = await unified_chat(req, user_id=user.id, db=db)
    assert res.action == "modify"
    # build kicked off because result["build"] and polygon_problem_id set
    assert "сборку" in res.response


@pytest.mark.asyncio
async def test_chat_executor_failure_becomes_error_message(db, user, task_session, monkeypatch):
    _stub_intent(monkeypatch, "edit_file", file_key="checker")

    async def boom(db_, session, message, resolved):
        raise RuntimeError("executor died")

    monkeypatch.setattr(mod.modify_executor, "execute", boom)

    req = ChatRequest(session_id=task_session.id, message="x")
    res = await unified_chat(req, user_id=user.id, db=db)
    assert res.is_error is True
    assert "Ошибка" in res.response


@pytest.mark.asyncio
async def test_chat_404(db, user, monkeypatch):
    req = ChatRequest(session_id="nope", message="x")
    with pytest.raises(HTTPException) as exc:
        await unified_chat(req, user_id=user.id, db=db)
    assert exc.value.status_code == 404
