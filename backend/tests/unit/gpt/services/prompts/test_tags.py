"""Unit tests for the algorithm-tags prompt (services.prompts.tags)."""
from api.user.gpt.services.prompts import tags


def test_system_prompt_requests_json_tags_in_english():
    text = tags.SYSTEM_PROMPT
    assert isinstance(text, str) and text
    assert '"tags"' in text
    assert "Codeforces" in text
    assert "английский" in text
