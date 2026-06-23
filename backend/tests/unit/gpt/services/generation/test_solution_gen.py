"""Unit tests for tag-based solution generation (generation.solution_gen)."""
import pytest

from api.user.gpt.services.generation import solution_gen as sol
from api.user.gpt.services.llm.client import llm


@pytest.mark.asyncio
async def test_generate_for_tag_returns_text(stub_llm):
    stub_llm(ask_text="int main(){}")
    out = await sol.generate_for_tag("MA", "main", {"name": "x"}, "model")
    assert out == "int main(){}"


@pytest.mark.asyncio
async def test_generate_for_tag_strips_code_fences(stub_llm):
    stub_llm(ask_text="```cpp\nint main(){}\n```")
    out = await sol.generate_for_tag("WA", "wrong", {}, "model")
    assert out == "int main(){}"
    assert "```" not in out


@pytest.mark.asyncio
async def test_generate_for_tag_builds_prompts(monkeypatch):
    captured = {}

    async def fake_ask_text(model, messages):
        captured["messages"] = messages
        return "code"

    monkeypatch.setattr(llm, "ask_text", fake_ask_text)
    await sol.generate_for_tag("TL", "slow", {"name": "P"}, "model")
    system = captured["messages"][0]["content"]
    user = captured["messages"][1]["content"]
    # ASCII code rule appended to the system prompt.
    from api.user.gpt.services.prompts.base import ASCII_CODE_RULE
    assert system.endswith(ASCII_CODE_RULE)
    # User prompt carries file name and the statement JSON.
    assert "Имя файла: slow" in user
    assert "Условие задачи" in user
