"""Unit tests for statement generation (generation.statement_gen)."""
import pytest
from fastapi import HTTPException

from api.user.gpt.services.generation import statement_gen as sg
from api.user.gpt.services.llm.client import llm


@pytest.mark.asyncio
async def test_generate_happy_path_returns_llm_json(stub_llm, monkeypatch):
    captured = {}

    async def fake_ask(model, messages, json_mode=True):
        captured["model"] = model
        captured["messages"] = messages
        captured["json_mode"] = json_mode
        return {"name": "Problem"}

    monkeypatch.setattr(llm, "ask", fake_ask)
    result = await sg.generate("my idea", "model-x", None, [])
    assert result == {"name": "Problem"}
    assert captured["json_mode"] is True
    # System prompt first, then user idea last.
    assert captured["messages"][0]["role"] == "system"
    assert captured["messages"][-1] == {"role": "user", "content": "my idea"}


@pytest.mark.asyncio
async def test_generate_uses_default_system_prompt(monkeypatch):
    from api.user.gpt.services.prompts.statement import SYSTEM_PROMPT

    captured = {}

    async def fake_ask(model, messages, json_mode=True):
        captured["messages"] = messages
        return {}

    monkeypatch.setattr(llm, "ask", fake_ask)
    await sg.generate("idea", "m", None, [])
    assert captured["messages"][0]["content"] == SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_generate_user_prompt_overrides_system(monkeypatch):
    captured = {}

    async def fake_ask(model, messages, json_mode=True):
        captured["messages"] = messages
        return {}

    monkeypatch.setattr(llm, "ask", fake_ask)
    await sg.generate("idea", "m", "CUSTOM SYS", [])
    assert captured["messages"][0]["content"] == "CUSTOM SYS"


@pytest.mark.asyncio
async def test_generate_prepends_problem_type_guide(monkeypatch):
    from models.task.session import ProblemType

    captured = {}

    async def fake_ask(model, messages, json_mode=True):
        captured["messages"] = messages
        return {}

    monkeypatch.setattr(llm, "ask", fake_ask)
    await sg.generate("idea", "m", "SYS", [], problem_type=ProblemType.INTERACTIVE)
    system = captured["messages"][0]["content"]
    assert "ИНТЕРАКТИВНАЯ" in system
    assert system.endswith("SYS")


@pytest.mark.asyncio
async def test_generate_includes_history(monkeypatch):
    captured = {}

    async def fake_ask(model, messages, json_mode=True):
        captured["messages"] = messages
        return {}

    monkeypatch.setattr(llm, "ask", fake_ask)
    history = [{"role": "user", "content": "prev"}, {"role": "assistant", "content": "reply"}]
    await sg.generate("idea", "m", "SYS", history)
    # system, history..., user
    assert captured["messages"][1:3] == history
    assert captured["messages"][-1]["content"] == "idea"


@pytest.mark.asyncio
async def test_generate_none_history_is_safe(monkeypatch):
    async def fake_ask(model, messages, json_mode=True):
        return {}

    monkeypatch.setattr(llm, "ask", fake_ask)
    assert await sg.generate("idea", "m", "SYS", None) == {}


@pytest.mark.asyncio
async def test_generate_raises_on_too_long_idea():
    big = "x" * (sg.MAX_IDEA_CHARS + 1)
    with pytest.raises(HTTPException) as exc:
        await sg.generate(big, "m", "SYS", [])
    assert exc.value.status_code == 400
