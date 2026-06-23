"""Unit tests for the task-modify chat prompts (services.prompts.task_modify)."""
from api.user.gpt.services.prompts import task_modify


def test_system_prompt_returns_json_of_changed_files():
    text = task_modify.SYSTEM_PROMPT
    assert isinstance(text, str) and text
    assert "JSON" in text
    assert "generator" in text
    assert "testlib.h" in text


def test_build_user_prompt_includes_files_and_message():
    out = task_modify.build_user_prompt(
        {"name": "Probe"},
        {"validator": "VAL-CODE", "checker": "CHK-CODE"},
        "please fix the checker",
    )
    assert "Probe" in out
    assert "VAL-CODE" in out and "CHK-CODE" in out
    assert "=== validator ===" in out and "=== checker ===" in out
    assert "please fix the checker" in out
