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


def test_package_wording_routes_to_build():
    # regression: "пересоздай пакет заново" was routed to regenerate and
    # replaced the whole task with an unrelated one
    assert "пересоздай пакет заново" in intent.SYSTEM_PROMPT
    assert "Never for a message that is only about the package" in intent.SYSTEM_PROMPT
