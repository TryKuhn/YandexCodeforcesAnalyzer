"""Unit tests for the answer-agent prompt (services.prompts.answer)."""
from api.user.gpt.services.prompts import answer


def test_system_prompt_is_answer_only_with_file_access():
    text = answer.SYSTEM_PROMPT
    assert isinstance(text, str) and text
    assert "Отвечай" in text
    # this turn answers but does not edit files itself
    assert "файлы сам не" in text
    # and it must see file contents (not deny access) and not deny real changes
    assert "содержимое" in text
    assert "НЕ утверждай, что изменений не было" in text
