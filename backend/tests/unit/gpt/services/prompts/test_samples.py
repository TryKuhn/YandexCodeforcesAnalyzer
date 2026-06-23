"""Unit tests for the sample-tests prompt builder (services.prompts.samples)."""
from api.user.gpt.services.prompts import samples


def test_build_system_prompt_mentions_count():
    out = samples.build_system_prompt(3)
    assert "3" in out
    assert "examples" in out


def test_build_system_prompt_varies_with_count():
    assert samples.build_system_prompt(2) != samples.build_system_prompt(5)
    assert "5" in samples.build_system_prompt(5)
