"""Unit tests for the intent-classifier prompt builder (services.prompts.intent)."""
from api.user.gpt.services.prompts import intent


def test_build_user_prompt_lists_files_and_context():
    out = intent.build_user_prompt("change checker", "the whole task",
                                   ["validator", "checker"])
    assert "validator, checker" in out
    assert "the whole task" in out
    assert "change checker" in out


def test_build_user_prompt_no_files():
    assert "(none yet)" in intent.build_user_prompt("hi", "ctx", [])


def test_actions_tuple_contains_core_actions():
    assert {"answer", "build", "regenerate", "edit_file"} <= set(intent.ACTIONS)
