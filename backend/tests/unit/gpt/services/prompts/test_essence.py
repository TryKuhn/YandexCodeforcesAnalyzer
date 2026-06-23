"""Unit tests for the essence-change detection prompt (services.prompts.essence)."""
from api.user.gpt.services.prompts import essence


def test_system_prompt_requires_json_with_essence_changed():
    text = essence.SYSTEM_PROMPT
    assert isinstance(text, str) and text
    assert "essence_changed" in text
    assert "dependents" in text


def test_build_user_prompt_includes_both_statements():
    out = essence.build_user_prompt("OLD-XYZ", "NEW-ABC")
    assert "OLD-XYZ" in out
    assert "NEW-ABC" in out
    assert "СТАРОЕ" in out and "НОВОЕ" in out
