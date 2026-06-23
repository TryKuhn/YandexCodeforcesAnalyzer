"""Unit tests for the test-planning prompt (services.prompts.test_plan)."""
from api.user.gpt.services.prompts import test_plan


def test_system_prompt_requests_json_params_and_seed():
    text = test_plan.SYSTEM_PROMPT
    assert isinstance(text, str) and text
    assert '"params"' in text
    assert "use_seed" in text
    assert "seed" in text
    assert "opt" in text
