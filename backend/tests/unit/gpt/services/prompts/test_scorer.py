"""Unit tests for the checker-scorer prompt (services.prompts.scorer)."""
from api.user.gpt.services.prompts import scorer
from api.user.gpt.services.prompts.base import NO_FENCES, TESTLIB_INTRO


def test_scorer_example_uses_testlib_and_quitp():
    example = scorer.SCORER_EXAMPLE
    assert isinstance(example, str) and example
    assert "testlib.h" in example
    assert "registerTestlibCmd" in example
    assert "quitp" in example


def test_system_prompt_describes_scorer_with_quitp_and_example():
    text = scorer.SYSTEM_PROMPT
    assert isinstance(text, str) and text
    assert "OUTPUT-ONLY" in text
    assert "quitp" in text
    assert scorer.SCORER_EXAMPLE in text
    assert TESTLIB_INTRO in text
    assert NO_FENCES in text
