"""Unit tests for the answer executor (services.chat.answer_executor)."""
import pytest

from api.user.gpt.services.chat import answer_executor as ae
from api.user.gpt.services.chat.context_resolver import ResolvedContext
from api.user.gpt.services.prompts import problem_type as ptg
from api.user.gpt.services.prompts.answer import SYSTEM_PROMPT
from models.task.session import ProblemType


def test_build_context_includes_statement_and_file():
    statement = {"name": "A+B", "legend": "add", "input": "two ints",
                 "output": "sum", "scoring": "ignored"}
    files = {"checker": "int main(){ return 0; }"}
    resolved = ResolvedContext(scope="file", file_key="checker", candidates=["checker"])

    parts = ae._build_context(statement, files, resolved)
    joined = "\n".join(parts)
    assert "ЗАДАЧА:" in joined
    assert "A+B" in joined and "add" in joined
    # statement summary excludes non-whitelisted keys
    assert "ignored" not in joined
    assert "ФАЙЛ (checker)" in joined
    assert "int main" in joined


def test_build_context_lists_files_when_not_file_scope():
    files = {"checker": "x", "validator": "y"}
    resolved = ResolvedContext(scope="task", candidates=["checker", "validator"])
    parts = ae._build_context({}, files, resolved)
    joined = "\n".join(parts)
    assert "Доступные файлы:" in joined
    assert "checker" in joined and "validator" in joined


@pytest.mark.asyncio
async def test_execute_builds_messages_and_returns_text(stub_llm, monkeypatch):
    captured = {}

    from api.user.gpt.services.llm.client import llm

    async def fake_ask_text(model, messages):
        captured["model"] = model
        captured["messages"] = messages
        return "the answer"

    monkeypatch.setattr(llm, "ask_text", fake_ask_text)

    resolved = ResolvedContext(scope="file", file_key="checker", candidates=["checker"])
    out = await ae.execute(
        message="как работает чекер?",
        statement={"name": "P", "legend": "L"},
        files={"checker": "code-here"},
        model="my-model",
        history=[{"role": "user", "content": "prev"}, {"role": "assistant", "content": "ans"}],
        resolved=resolved,
        problem_type=None,
    )
    assert out == "the answer"
    assert captured["model"] == "my-model"
    msgs = captured["messages"]
    # system prompt is plain SYSTEM_PROMPT when problem_type is None
    assert msgs[0] == {"role": "system", "content": SYSTEM_PROMPT}
    # history is carried over
    assert {"role": "user", "content": "prev"} in msgs
    # last user message includes context + question
    user_msg = msgs[-1]["content"]
    assert "ВОПРОС: как работает чекер?" in user_msg
    assert "ЗАДАЧА:" in user_msg
    assert "ФАЙЛ (checker)" in user_msg


@pytest.mark.asyncio
async def test_execute_prepends_problem_type_guide(monkeypatch):
    captured = {}
    from api.user.gpt.services.llm.client import llm

    async def fake_ask_text(model, messages):
        captured["messages"] = messages
        return "ok"

    monkeypatch.setattr(llm, "ask_text", fake_ask_text)
    resolved = ResolvedContext(scope="task", candidates=[])
    await ae.execute("hi", {}, {}, "m", [], resolved, problem_type=ProblemType.REGULAR)

    system = captured["messages"][0]["content"]
    assert ptg.guide(ProblemType.REGULAR) in system
    assert SYSTEM_PROMPT in system


@pytest.mark.asyncio
async def test_execute_fallback_when_empty(monkeypatch):
    from api.user.gpt.services.llm.client import llm

    async def fake_ask_text(model, messages):
        return ""

    monkeypatch.setattr(llm, "ask_text", fake_ask_text)
    resolved = ResolvedContext(scope="task", candidates=[])
    out = await ae.execute("hi", {}, {}, "m", [], resolved)
    assert out == "Не удалось получить ответ."


@pytest.mark.asyncio
async def test_execute_no_context_passes_bare_message(monkeypatch):
    captured = {}
    from api.user.gpt.services.llm.client import llm

    async def fake_ask_text(model, messages):
        captured["messages"] = messages
        return "ok"

    monkeypatch.setattr(llm, "ask_text", fake_ask_text)
    resolved = ResolvedContext(scope="task", candidates=[])
    await ae.execute("just a question", {}, {}, "m", [], resolved)
    assert captured["messages"][-1]["content"] == "just a question"
