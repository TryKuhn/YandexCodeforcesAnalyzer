"""Unit tests for the Scoring LaTeX-table prompt (services.prompts.scoring)."""
from api.user.gpt.services.prompts import scoring


def test_system_prompt_builds_latex_subtask_table():
    text = scoring.SYSTEM_PROMPT
    assert isinstance(text, str) and text
    assert "Scoring" in text
    assert "tabular" in text
    assert "Подзадача" in text
    assert "100" in text
