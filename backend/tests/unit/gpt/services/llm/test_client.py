"""Unit tests for the LLM client helpers (services.llm.client)."""
from api.user.gpt.services.llm.client import strip_code_fences


def test_strip_code_fences_removes_language_fence():
    assert strip_code_fences("```cpp\nint main(){}\n```") == "int main(){}"


def test_strip_code_fences_removes_bare_fence():
    assert strip_code_fences("```\nhello\n```") == "hello"


def test_strip_code_fences_plain_passthrough():
    assert strip_code_fences("just text") == "just text"
