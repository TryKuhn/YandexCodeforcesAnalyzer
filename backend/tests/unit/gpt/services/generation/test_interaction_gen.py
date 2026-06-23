"""Unit tests for interaction-section generation (generation.interaction_gen)."""
import pytest

from api.user.gpt.services.generation import interaction_gen as ig
from api.user.gpt.services.llm.client import llm


@pytest.mark.asyncio
async def test_generate_returns_text(stub_llm):
    stub_llm(ask_text="Взаимодействие происходит так...")
    out = await ig.generate({"name": "x"}, "model")
    assert out == "Взаимодействие происходит так..."


@pytest.mark.asyncio
async def test_generate_builds_messages(monkeypatch):
    from api.user.gpt.services.prompts.interaction import SYSTEM_PROMPT

    captured = {}

    async def fake_ask_text(model, messages):
        captured["messages"] = messages
        return "ok"

    monkeypatch.setattr(llm, "ask_text", fake_ask_text)
    await ig.generate({"name": "P"}, "model")
    assert captured["messages"][0]["content"] == SYSTEM_PROMPT
    assert "Условие задачи" in captured["messages"][1]["content"]
    assert '"name": "P"' in captured["messages"][1]["content"]


@pytest.mark.asyncio
async def test_generate_does_not_strip_fences(stub_llm):
    # interaction_gen returns the raw text (no strip_code_fences).
    stub_llm(ask_text="```\ntext\n```")
    out = await ig.generate({}, "model")
    assert out == "```\ntext\n```"
