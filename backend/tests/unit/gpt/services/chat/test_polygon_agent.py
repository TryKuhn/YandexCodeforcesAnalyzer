"""Unit tests for the read-only Polygon tool-calling agent (services.chat.polygon_agent).

The agent talks to OpenRouter via httpx directly (not the llm client), so we
replace httpx.AsyncClient in the module with a fake that returns a scripted
sequence of chat-completion responses. Live-read tools (get_file / get_solutions
/ get_solution_content) go through ``get_user`` + ``polygon_call`` which we patch
in the module namespace; cache-backed tools use the real ``db`` fixture.
"""
import base64
import json

import pytest
from fastapi import HTTPException

from api.user.gpt.services.chat import polygon_agent as pa
from models.task.problem import PolygonProblem
from models.task.statement import PolygonStatement
from models.task.test import PolygonTest


# ── fake OpenRouter client ──────────────────────────────────────────────────

class _Resp:
    def __init__(self, body, status_code=200, text=""):
        self._body = body
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._body


def _msg_text(content):
    return {"choices": [{"finish_reason": "stop", "message": {"content": content}}]}


def _msg_tool_call(call_id, name, args):
    return {"choices": [{"finish_reason": "tool_calls", "message": {
        "role": "assistant", "content": None,
        "tool_calls": [{"id": call_id, "type": "function",
                        "function": {"name": name, "arguments": json.dumps(args)}}]}}]}


def _install_client(monkeypatch, responses):
    """Patch httpx.AsyncClient with a fake yielding ``responses`` in order."""
    state = {"i": 0, "posts": []}

    class _FakeClient:
        def __init__(self, *a, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, url, headers=None, json=None):
            state["posts"].append(json)
            r = responses[state["i"]]
            state["i"] += 1
            return r

    monkeypatch.setattr(pa.httpx, "AsyncClient", _FakeClient)
    return state


@pytest.mark.asyncio
async def test_run_agent_plain_answer(db, task_session, user, monkeypatch):
    state = _install_client(monkeypatch, [_Resp(_msg_text("Привет!"))])
    out = await pa.run_agent(db, task_session, user.id, "вопрос", "m", attachments=[])
    assert out == "Привет!"
    # history persisted: user then assistant
    assert task_session.history[-1] == {"role": "assistant", "content": "Привет!"}
    assert task_session.history[0]["role"] == "user"
    # chat_log got 2 entries
    assert len(task_session.chat_log) == 2
    # system prompt sent as first message
    assert state["posts"][0]["messages"][0]["role"] == "system"


@pytest.mark.asyncio
async def test_run_agent_attachments_appended(db, task_session, user, monkeypatch):
    state = _install_client(monkeypatch, [_Resp(_msg_text("ok"))])
    await pa.run_agent(db, task_session, user.id, "base question", "m",
                       attachments=[{"label": "файл", "content": "XYZ"}])
    sent_user = state["posts"][0]["messages"][-1]["content"]
    assert "base question" in sent_user
    assert "файл" in sent_user and "XYZ" in sent_user


@pytest.mark.asyncio
async def test_run_agent_tool_loop_then_answer(db, task_session, user, monkeypatch):
    # First response asks for a tool, second returns final text.
    responses = [
        _Resp(_msg_tool_call("c1", "get_problem_info", {})),
        _Resp(_msg_text("итог")),
    ]
    state = _install_client(monkeypatch, responses)

    # seed the cache so get_problem_info has data
    problem = PolygonProblem(user_id=user.id, polygon_id=task_session.polygon_problem_id,
                             owner="o", name="n", input_file="in", output_file="out",
                             interactive=False, well_formed=True,
                             time_limit=1000, memory_limit=256)
    db.add(problem)
    await db.commit()

    out = await pa.run_agent(db, task_session, user.id, "инфо?", "m", attachments=[])
    assert out == "итог"
    # second request should contain a tool-result message
    second_msgs = state["posts"][1]["messages"]
    assert any(m.get("role") == "tool" for m in second_msgs)
    tool_msg = next(m for m in second_msgs if m.get("role") == "tool")
    assert json.loads(tool_msg["content"])["timeLimit"] == 1000


@pytest.mark.asyncio
async def test_run_agent_non_200_raises(db, task_session, user, monkeypatch):
    _install_client(monkeypatch, [_Resp(None, status_code=500, text="boom")])
    with pytest.raises(HTTPException) as ei:
        await pa.run_agent(db, task_session, user.id, "q", "m", attachments=[])
    assert ei.value.status_code == 500


@pytest.mark.asyncio
async def test_run_agent_no_answer_fallback(db, task_session, user, monkeypatch):
    # Always asks for a tool → loop exhausts MAX_TOOL_ROUNDS with no final text.
    responses = [_Resp(_msg_tool_call(f"c{i}", "get_problem_info", {}))
                 for i in range(pa.MAX_TOOL_ROUNDS)]
    _install_client(monkeypatch, responses)
    # no cached problem → tool returns "Problem not found in cache." each round
    out = await pa.run_agent(db, task_session, user.id, "q", "m", attachments=[])
    assert out == "Не удалось получить ответ от агента."


@pytest.mark.asyncio
async def test_run_agent_bad_tool_arguments_default_empty(db, task_session, user, monkeypatch):
    # malformed arguments JSON → tool_args = {}; still dispatches.
    bad = {"choices": [{"finish_reason": "tool_calls", "message": {
        "role": "assistant", "content": None,
        "tool_calls": [{"id": "c1", "type": "function",
                        "function": {"name": "get_problem_info",
                                     "arguments": "{not json"}}]}}]}
    _install_client(monkeypatch, [_Resp(bad), _Resp(_msg_text("done"))])
    out = await pa.run_agent(db, task_session, user.id, "q", "m", attachments=[])
    assert out == "done"


# ── _execute_tool branches ──────────────────────────────────────────────────

async def _seed_problem(db, user, polygon_id=555):
    problem = PolygonProblem(user_id=user.id, polygon_id=polygon_id, owner="o",
                             name="n", input_file="in.txt", output_file="out.txt",
                             interactive=True, well_formed=True,
                             time_limit=2000, memory_limit=512)
    db.add(problem)
    await db.commit()
    await db.refresh(problem)
    return problem


@pytest.mark.asyncio
async def test_execute_tool_problem_not_in_cache(db, user):
    out = await pa._execute_tool("get_problem_info", {}, 999, db, user.id)
    assert out == "Problem not found in cache."


@pytest.mark.asyncio
async def test_execute_tool_problem_info(db, user):
    await _seed_problem(db, user)
    out = await pa._execute_tool("get_problem_info", {}, 555, db, user.id)
    data = json.loads(out)
    assert data["inputFile"] == "in.txt"
    assert data["interactive"] is True
    assert data["timeLimit"] == 2000


@pytest.mark.asyncio
async def test_execute_tool_statement_found_and_missing(db, user):
    problem = await _seed_problem(db, user)
    stmt = PolygonStatement(problem_id=problem.id, lang="russian", name="Имя",
                            legend="leg", input="i", output="o", scoring="s",
                            interaction="x", notes="n", tutorial="t")
    db.add(stmt)
    await db.commit()

    found = await pa._execute_tool("get_statement", {"lang": "russian"}, 555, db, user.id)
    assert json.loads(found)["name"] == "Имя"

    missing = await pa._execute_tool("get_statement", {"lang": "english"}, 555, db, user.id)
    assert "not found" in missing


@pytest.mark.asyncio
async def test_execute_tool_get_tests_with_input(db, user):
    problem = await _seed_problem(db, user)
    raw = "1 2 3"
    t = PolygonTest(problem_id=problem.id, testset="tests", index=1,
                    input_b64=base64.b64encode(raw.encode()).decode(),
                    group="g1", points=10.0, use_in_statements=True)
    db.add(t)
    await db.commit()

    out = await pa._execute_tool("get_tests", {"limit": 5}, 555, db, user.id)
    data = json.loads(out)
    assert data[0]["index"] == 1
    assert data[0]["input"] == raw
    assert data[0]["group"] == "g1"


@pytest.mark.asyncio
async def test_execute_tool_get_tests_empty(db, user):
    await _seed_problem(db, user)
    out = await pa._execute_tool("get_tests", {}, 555, db, user.id)
    assert "No tests in cache" in out


@pytest.mark.asyncio
async def test_execute_tool_get_file_live(db, user, monkeypatch):
    async def fake_get_user(uid, db):
        return object()

    async def fake_polygon_call(method, params, user):
        assert method == "problem.viewFile"
        return {"message": "file-content"}

    monkeypatch.setattr(pa, "get_user", fake_get_user)
    monkeypatch.setattr(pa, "polygon_call", fake_polygon_call)
    out = await pa._execute_tool("get_file", {"file_type": "source", "name": "a.cpp"},
                                 555, db, user.id)
    assert out == "file-content"


@pytest.mark.asyncio
async def test_execute_tool_get_solutions_live(db, user, monkeypatch):
    async def fake_get_user(uid, db):
        return object()

    async def fake_polygon_call(method, params, user):
        return [{"name": "main.cpp", "tag": "MA"}, {"name": "bad.cpp", "tag": "WA"}]

    monkeypatch.setattr(pa, "get_user", fake_get_user)
    monkeypatch.setattr(pa, "polygon_call", fake_polygon_call)
    out = await pa._execute_tool("get_solutions", {}, 555, db, user.id)
    data = json.loads(out)
    assert {"name": "main.cpp", "tag": "MA"} in data


@pytest.mark.asyncio
async def test_execute_tool_get_solution_content_live(db, user, monkeypatch):
    async def fake_get_user(uid, db):
        return object()

    async def fake_polygon_call(method, params, user):
        return {"message": "int main(){}"}

    monkeypatch.setattr(pa, "get_user", fake_get_user)
    monkeypatch.setattr(pa, "polygon_call", fake_polygon_call)
    out = await pa._execute_tool("get_solution_content", {"name": "main.cpp"},
                                 555, db, user.id)
    assert out == "int main(){}"


@pytest.mark.asyncio
async def test_execute_tool_error_is_caught(db, user, monkeypatch):
    async def boom(uid, db):
        raise RuntimeError("network")

    monkeypatch.setattr(pa, "get_user", boom)
    out = await pa._execute_tool("get_file", {"file_type": "source", "name": "a"},
                                 555, db, user.id)
    assert out.startswith("Tool error:")


@pytest.mark.asyncio
async def test_execute_tool_unknown_returns_unknown(db, user):
    out = await pa._execute_tool("nonexistent_tool", {}, 555, db, user.id)
    assert out == "Unknown tool"
