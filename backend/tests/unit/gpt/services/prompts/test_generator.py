"""Unit tests for the generator prompts (services.prompts.generator)."""
from api.user.gpt.services.prompts import generator
from api.user.gpt.services.prompts.base import NO_FENCES, TESTLIB_INTRO


def test_system_prompt_describes_generator_and_opt_rules():
    text = generator.SYSTEM_PROMPT
    assert isinstance(text, str) and text
    assert "generator.cpp" in text
    assert "registerGen" in text
    assert "opt" in text
    assert TESTLIB_INTRO in text
    assert NO_FENCES in text


def test_build_user_prompt_includes_statement():
    out = generator.build_user_prompt({"name": "Magic Sum"})
    assert "Magic Sum" in out
    assert "Условие задачи" in out


def test_build_user_prompt_includes_plan_when_given():
    out = generator.build_user_prompt({"name": "X"}, plan_text="PLAN-PARAM-n")
    assert "PLAN-PARAM-n" in out
    assert "opt" in out


def test_build_user_prompt_omits_plan_when_absent():
    out = generator.build_user_prompt({"name": "X"})
    assert "Реализуй чтение" not in out
