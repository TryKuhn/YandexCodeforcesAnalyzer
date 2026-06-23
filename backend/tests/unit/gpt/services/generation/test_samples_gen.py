"""Unit tests for sample-test generation (generation.samples_gen)."""
import pytest

from api.user.gpt.services.generation import samples_gen as sm


@pytest.mark.asyncio
async def test_generate_maps_examples(stub_llm):
    stub_llm(ask={"examples": [
        {"input": "1 2", "output": "3"},
        {"input": "4", "output": "5"},
    ]})
    out = await sm.generate({"name": "x"}, "model")
    assert out == [
        {"input": "1 2", "output": "3"},
        {"input": "4", "output": "5"},
    ]


@pytest.mark.asyncio
async def test_generate_coerces_values_to_str(stub_llm):
    stub_llm(ask={"examples": [{"input": 7, "output": 8}]})
    out = await sm.generate({}, "model")
    assert out == [{"input": "7", "output": "8"}]


@pytest.mark.asyncio
async def test_generate_missing_keys_default_empty(stub_llm):
    stub_llm(ask={"examples": [{}]})
    out = await sm.generate({}, "model")
    assert out == [{"input": "", "output": ""}]


@pytest.mark.asyncio
async def test_generate_no_examples_key_returns_empty(stub_llm):
    stub_llm(ask={})
    assert await sm.generate({}, "model") == []


@pytest.mark.asyncio
async def test_generate_passes_count_into_system_prompt(monkeypatch):
    from api.user.gpt.services.llm.client import llm

    captured = {}

    async def fake_ask(model, messages, json_mode=True):
        captured["messages"] = messages
        return {"examples": []}

    monkeypatch.setattr(llm, "ask", fake_ask)
    await sm.generate({"name": "x"}, "model", count=7)
    # System prompt built with count; user prompt carries the statement JSON.
    assert captured["messages"][0]["role"] == "system"
    assert "Условие задачи" in captured["messages"][1]["content"]
