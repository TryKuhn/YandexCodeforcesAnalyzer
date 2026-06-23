"""Unit tests for the technical-file taxonomy (services.files.file_registry)."""
from api.user.gpt.services.files.file_registry import (applicable_types, category,
                                                       get_spec, solution_tag)
from models.task.session import ProblemType


def test_regular_excludes_interactor_and_scorer():
    types = applicable_types(ProblemType.REGULAR)
    assert "interactor" not in types and "scorer" not in types
    assert {"validator", "generator", "script", "checker"} <= set(types)


def test_interactive_includes_interactor():
    assert "interactor" in applicable_types(ProblemType.INTERACTIVE)


def test_output_only_includes_scorer_and_jury_not_checker():
    types = applicable_types(ProblemType.OUTPUT_ONLY)
    assert "scorer" in types and "jury_answer" in types
    assert "checker" not in types


def test_applicable_types_accepts_plain_string():
    assert applicable_types("regular") == applicable_types(ProblemType.REGULAR)


def test_scorer_category_is_checker():
    assert category("scorer") == "checker"


def test_solution_tags():
    assert solution_tag("solution_cpp") == "MA"
    assert solution_tag("solution_py") == "OK"
    assert solution_tag("wa_sol") == "WA"


def test_unknown_type_returns_none():
    assert get_spec("unknown") is None
    assert category("unknown") is None
    assert solution_tag("unknown") is None
