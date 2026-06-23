"""Unit tests for the shared prompt fragments (services.prompts.base)."""
from api.user.gpt.services.prompts import base


def test_latex_formatting_mentions_textbf_and_forbids_markdown():
    assert isinstance(base.LATEX_FORMATTING, str) and base.LATEX_FORMATTING
    assert "\\textbf" in base.LATEX_FORMATTING
    assert "LaTeX" in base.LATEX_FORMATTING


def test_no_fences_forbids_markdown_fences():
    assert isinstance(base.NO_FENCES, str) and base.NO_FENCES
    assert "```" in base.NO_FENCES
    assert "markdown" in base.NO_FENCES.lower()


def test_ascii_code_rule_mentions_ascii_and_english():
    assert isinstance(base.ASCII_CODE_RULE, str) and base.ASCII_CODE_RULE
    assert "ASCII" in base.ASCII_CODE_RULE
    assert "английском" in base.ASCII_CODE_RULE


def test_testlib_intro_mentions_testlib_include():
    assert isinstance(base.TESTLIB_INTRO, str) and base.TESTLIB_INTRO
    assert "testlib.h" in base.TESTLIB_INTRO


def test_incorrect_solution_rules_cover_verdicts():
    text = base.INCORRECT_SOLUTION_RULES
    assert isinstance(text, str) and text
    for verdict in ("TL", "ML", "WA", "RE"):
        assert verdict in text


def test_freemarker_tutorial_mentions_directives():
    text = base.FREEMARKER_TUTORIAL
    assert isinstance(text, str) and text
    assert "Freemarker" in text
    assert "#assign" in text
    assert "#list" in text
