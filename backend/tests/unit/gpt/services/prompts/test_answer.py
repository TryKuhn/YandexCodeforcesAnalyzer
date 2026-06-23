"""Unit tests for the answer-agent prompt (services.prompts.answer)."""
from api.user.gpt.services.prompts import answer


def test_system_prompt_is_answer_only_no_changes():
    text = answer.SYSTEM_PROMPT
    assert isinstance(text, str) and text
    assert "Не вноси никаких изменений" in text
    assert "Отвечай" in text
