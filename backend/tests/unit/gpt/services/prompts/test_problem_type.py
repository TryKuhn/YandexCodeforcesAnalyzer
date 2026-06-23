"""Unit tests for the problem-type guidance block (services.prompts.problem_type)."""
from api.user.gpt.services.prompts import problem_type as pt
from models.task.session import ProblemType


def test_regular_guide():
    text = pt.guide(ProblemType.REGULAR)
    assert "ОБЫЧНАЯ" in text and "ИНТЕРАКТОР НЕ НУЖЕН" in text


def test_interactive_guide():
    assert "ИНТЕРАКТИВНАЯ" in pt.guide(ProblemType.INTERACTIVE)


def test_output_only_guide():
    assert "OUTPUT-ONLY" in pt.guide(ProblemType.OUTPUT_ONLY)


def test_guide_accepts_plain_string():
    assert pt.guide("interactive") == pt.guide(ProblemType.INTERACTIVE)


def test_guide_bad_input_defaults_to_regular():
    assert pt.guide("nonsense") == pt.guide(ProblemType.REGULAR)
