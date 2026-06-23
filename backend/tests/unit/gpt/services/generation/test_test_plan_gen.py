"""Unit tests for test-plan generation (generation.test_plan_gen)."""
import pytest

from api.user.gpt.services.generation import test_plan_gen as tpg
from api.user.gpt.services.llm.client import llm


@pytest.mark.asyncio
async def test_generate_normalises_params(stub_llm):
    stub_llm(ask={
        "params": [
            {"name": "n", "type": "int", "description": "size"},
            {"name": "m"},               # missing type/description -> defaults
            {"type": "int"},             # no name -> dropped
            "not-a-dict",                # not a dict -> dropped
        ],
        "use_seed": 1,
        "strategy": "random",
    })
    plan = await tpg.generate({"name": "x"}, "model")
    assert plan["params"] == [
        {"name": "n", "type": "int", "description": "size"},
        {"name": "m", "type": "int", "description": ""},
    ]
    assert plan["use_seed"] is True
    assert plan["strategy"] == "random"


@pytest.mark.asyncio
async def test_generate_defaults_when_keys_missing(stub_llm):
    stub_llm(ask={})
    plan = await tpg.generate({}, "model")
    assert plan == {"params": [], "use_seed": False, "strategy": ""}


@pytest.mark.asyncio
async def test_generate_returns_default_on_llm_error(monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("down")

    monkeypatch.setattr(llm, "ask", boom)
    plan = await tpg.generate({}, "model")
    assert plan == {"params": [], "use_seed": False, "strategy": ""}


def test_format_plan_empty_returns_blank():
    assert tpg.format_plan({}) == ""
    assert tpg.format_plan({"params": []}) == ""


def test_format_plan_lists_params_and_seed_and_strategy():
    plan = {
        "params": [{"name": "n", "type": "int", "description": "array size"}],
        "use_seed": True,
        "strategy": "edge cases",
    }
    text = tpg.format_plan(plan)
    assert "План тестов" in text
    assert "n (int): array size" in text
    assert "seed НУЖЕН" in text
    assert "Стратегия тестов: edge cases" in text


def test_format_plan_omits_seed_line_when_false():
    plan = {"params": [{"name": "n", "type": "int", "description": "d"}], "use_seed": False}
    text = tpg.format_plan(plan)
    assert "seed НУЖЕН" not in text
