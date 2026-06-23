"""Unit tests for scoring-section generation (generation.scoring_gen)."""
import pytest

from api.user.gpt.services.generation import scoring_gen as sc
from api.user.gpt.services.llm.client import llm


@pytest.mark.asyncio
async def test_output_only_uses_output_prompt(monkeypatch):
    from api.user.gpt.services.prompts.output_scoring import \
        SYSTEM_PROMPT as OUTPUT_SYSTEM_PROMPT

    captured = {}

    async def fake_ask_text(model, messages):
        captured["messages"] = messages
        return "scorer rules"

    monkeypatch.setattr(llm, "ask_text", fake_ask_text)
    out = await sc.generate({"name": "x"}, "m", False, False, problem_type="output_only")
    assert out == "scorer rules"
    assert captured["messages"][0]["content"] == OUTPUT_SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_no_groups_no_points_returns_empty(stub_llm):
    stub_llm(ask_text="should not be used")
    out = await sc.generate({"name": "x"}, "m", False, False)
    assert out == ""


@pytest.mark.asyncio
async def test_groups_enabled_calls_llm(monkeypatch):
    from api.user.gpt.services.prompts.scoring import SYSTEM_PROMPT

    captured = {}

    async def fake_ask_text(model, messages):
        captured["messages"] = messages
        return "table latex"

    monkeypatch.setattr(llm, "ask_text", fake_ask_text)
    out = await sc.generate({"name": "x"}, "m", True, False)
    assert out == "table latex"
    assert captured["messages"][0]["content"] == SYSTEM_PROMPT


@pytest.mark.asyncio
async def test_points_only_enabled_calls_llm(stub_llm):
    stub_llm(ask_text="points")
    out = await sc.generate({"name": "x"}, "m", False, True)
    assert out == "points"


@pytest.mark.asyncio
async def test_regular_problem_type_not_treated_as_output(stub_llm):
    stub_llm(ask_text="regular table")
    out = await sc.generate({}, "m", True, True, problem_type="regular")
    assert out == "regular table"
