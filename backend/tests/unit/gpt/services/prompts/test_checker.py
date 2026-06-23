"""Unit tests for the checker prompts (services.prompts.checker)."""
from api.user.gpt.services.prompts import checker
from api.user.gpt.services.prompts.base import NO_FENCES, TESTLIB_INTRO


def test_system_prompt_describes_checker_and_includes_fragments():
    text = checker.SYSTEM_PROMPT
    assert isinstance(text, str) and text
    assert "checker.cpp" in text
    assert "registerTestlibCmd" in text
    assert TESTLIB_INTRO in text
    assert NO_FENCES in text


def test_interactive_system_prompt_mentions_interactor():
    text = checker.INTERACTIVE_SYSTEM_PROMPT
    assert isinstance(text, str) and text
    assert "ИНТЕРАКТИВНОЙ" in text
    assert "интерактор" in text
    assert NO_FENCES in text
