"""Unit tests for the jury reference-solver prompt (services.prompts.jury_answer)."""
from api.user.gpt.services.prompts import jury_answer
from api.user.gpt.services.prompts.base import NO_FENCES


def test_system_prompt_describes_jury_solution():
    text = jury_answer.SYSTEM_PROMPT
    assert isinstance(text, str) and text
    assert "OUTPUT-ONLY" in text
    assert "эталонное" in text
    assert NO_FENCES in text
