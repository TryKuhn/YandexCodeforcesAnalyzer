"""Unit tests for the interactor prompt (services.prompts.interactor)."""
from api.user.gpt.services.prompts import interactor
from api.user.gpt.services.prompts.base import NO_FENCES, TESTLIB_INTRO


def test_system_prompt_describes_interactor():
    text = interactor.SYSTEM_PROMPT
    assert isinstance(text, str) and text
    assert "interactor.cpp" in text
    assert "registerInteraction" in text
    assert TESTLIB_INTRO in text
    assert NO_FENCES in text
