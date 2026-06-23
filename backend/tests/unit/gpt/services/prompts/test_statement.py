"""Unit tests for the statement-generation prompt (services.prompts.statement)."""
from api.user.gpt.services.prompts import statement
from api.user.gpt.services.prompts.base import LATEX_FORMATTING


def test_system_prompt_outputs_json_and_uses_latex():
    text = statement.SYSTEM_PROMPT
    assert isinstance(text, str) and text
    assert "JSON" in text
    assert "legend" in text and "tutorial" in text
    assert LATEX_FORMATTING in text
