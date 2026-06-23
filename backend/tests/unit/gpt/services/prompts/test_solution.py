"""Unit tests for the solution prompt builder (services.prompts.solution)."""
import pytest

from api.user.gpt.services.prompts import solution
from api.user.gpt.services.prompts.base import INCORRECT_SOLUTION_RULES, NO_FENCES


def test_build_system_prompt_main_solution_has_no_incorrect_rules():
    out = solution.build_system_prompt("MA")
    assert solution.TAG_DESCRIPTIONS["MA"] in out
    assert INCORRECT_SOLUTION_RULES not in out
    assert NO_FENCES in out


@pytest.mark.parametrize("tag", ["WA", "TL", "ML", "RE", "RJ"])
def test_build_system_prompt_incorrect_tags_include_rules(tag):
    out = solution.build_system_prompt(tag)
    assert solution.TAG_DESCRIPTIONS[tag] in out
    assert INCORRECT_SOLUTION_RULES in out


def test_build_system_prompt_varies_by_tag():
    assert solution.build_system_prompt("MA") != solution.build_system_prompt("WA")


def test_build_system_prompt_unknown_tag_falls_back():
    out = solution.build_system_prompt("ZZ")
    assert "ZZ" in out
    assert NO_FENCES in out
