"""Unit tests for the validator prompt (services.prompts.validator)."""
from api.user.gpt.services.prompts import validator
from api.user.gpt.services.prompts.base import NO_FENCES, TESTLIB_INTRO


def test_system_prompt_describes_validator():
    text = validator.SYSTEM_PROMPT
    assert isinstance(text, str) and text
    assert "validator.cpp" in text
    assert "registerValidation" in text
    assert "readEof" in text
    assert TESTLIB_INTRO in text
    assert NO_FENCES in text
