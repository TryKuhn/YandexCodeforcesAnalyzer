"""Unit tests for the code-fixing prompt builder (services.prompts.fix)."""
from api.user.gpt.services.prompts import fix


def test_build_system_prompt_includes_component_and_error():
    out = fix.build_system_prompt("validator", "compile error XYZ")
    assert "validator" in out
    assert "compile error XYZ" in out
    assert "Return ONLY the corrected code" in out


def test_build_system_prompt_without_history_or_related():
    out = fix.build_system_prompt("checker", "boom")
    assert "ПРЕДЫДУЩИЕ ПОПЫТКИ" not in out
    assert "связанные файлы" not in out


def test_build_system_prompt_lists_previous_errors():
    out = fix.build_system_prompt("checker", "err", previous_errors=["e1", "e2"])
    assert "ПРЕДЫДУЩИЕ ПОПЫТКИ" in out
    assert "e1" in out and "e2" in out


def test_build_system_prompt_lists_related_files():
    out = fix.build_system_prompt(
        "checker", "err", related_files={"validator": "code", "generator": "code"}
    )
    assert "validator" in out and "generator" in out
    assert "НЕ переписывай их" in out


def test_build_system_prompt_generator_gets_opt_key_hint():
    out = fix.build_system_prompt(
        "generator", "unused key", related_files={"script": "code"}
    )
    assert "opt" in out
    assert "seed" in out
