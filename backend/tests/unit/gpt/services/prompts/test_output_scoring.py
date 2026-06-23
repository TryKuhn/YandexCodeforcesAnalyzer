"""Unit tests for the output-only Scoring section prompt (services.prompts.output_scoring)."""
from api.user.gpt.services.prompts import output_scoring


def test_system_prompt_describes_output_only_scoring():
    text = output_scoring.SYSTEM_PROMPT
    assert isinstance(text, str) and text
    assert "OUTPUT-ONLY" in text
    assert "Система оценивания" in text
    assert "quitp" in text
    assert "\\textbf" in text
