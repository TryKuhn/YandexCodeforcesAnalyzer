"""Unit tests for the algorithm-tag suggester (services.generation.tags_gen)."""
import pytest

from api.user.gpt.services.generation import tags_gen


@pytest.mark.asyncio
async def test_suggest_returns_tag_list(stub_llm):
    stub_llm(ask={"tags": ["dp", "greedy", "math"]})
    out = await tags_gen.suggest({"name": "P", "legend": "..."}, "m")
    assert out == ["dp", "greedy", "math"]


@pytest.mark.asyncio
async def test_suggest_filters_falsy_and_stringifies(stub_llm):
    stub_llm(ask={"tags": ["dp", "", None, 0, 42, "trees"]})
    out = await tags_gen.suggest({}, "m")
    # empty string, None, 0 are filtered; 42 stringified
    assert out == ["dp", "42", "trees"]


@pytest.mark.asyncio
async def test_suggest_missing_tags_key_returns_empty(stub_llm):
    stub_llm(ask={"something_else": []})
    out = await tags_gen.suggest({}, "m")
    assert out == []


@pytest.mark.asyncio
async def test_suggest_builds_system_and_user_messages(monkeypatch):
    from api.user.gpt.services.llm.client import llm
    from api.user.gpt.services.prompts.tags import SYSTEM_PROMPT

    captured = {}

    async def fake_ask(model, messages, json_mode=True):
        captured["model"] = model
        captured["messages"] = messages
        return {"tags": ["x"]}

    monkeypatch.setattr(llm, "ask", fake_ask)
    await tags_gen.suggest({"name": "Задача"}, "my-model")

    assert captured["model"] == "my-model"
    msgs = captured["messages"]
    assert msgs[0] == {"role": "system", "content": SYSTEM_PROMPT}
    # statement serialised with ensure_ascii=False (cyrillic preserved)
    assert "Задача" in msgs[1]["content"]
    assert msgs[1]["role"] == "user"
