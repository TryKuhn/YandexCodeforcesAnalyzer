"""Unit tests for the Freemarker script prompts (services.prompts.script)."""
from api.user.gpt.services.prompts import script
from api.user.gpt.services.prompts.base import FREEMARKER_TUTORIAL


def test_script_example_calls_generator_without_extension():
    example = script.SCRIPT_EXAMPLE
    assert isinstance(example, str) and example
    assert "generator" in example
    assert "generator.cpp" not in example


def test_system_prompt_includes_tutorial_and_generator_naming():
    text = script.SYSTEM_PROMPT
    assert isinstance(text, str) and text
    assert FREEMARKER_TUTORIAL in text
    assert "generator" in text
    assert script.SCRIPT_EXAMPLE in text


def test_build_user_prompt_includes_statement():
    out = script.build_user_prompt({"name": "Foo Bar"})
    assert "Foo Bar" in out


def test_build_user_prompt_includes_generator_code_and_plan():
    out = script.build_user_prompt(
        {"name": "X"}, generator_code="GEN-CODE-123", plan_text="PLAN-XYZ"
    )
    assert "GEN-CODE-123" in out
    assert "PLAN-XYZ" in out


def test_build_user_prompt_omits_generator_when_absent():
    out = script.build_user_prompt({"name": "X"})
    assert "Код генератора" not in out
