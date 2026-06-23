"""Unit tests for the Interaction-section prompt (services.prompts.interaction)."""
from api.user.gpt.services.prompts import interaction
from api.user.gpt.services.prompts.base import LATEX_FORMATTING


def test_system_prompt_describes_interaction_section():
    text = interaction.SYSTEM_PROMPT
    assert isinstance(text, str) and text
    assert "Взаимодействие" in text
    assert "протокол" in text
    assert LATEX_FORMATTING in text
