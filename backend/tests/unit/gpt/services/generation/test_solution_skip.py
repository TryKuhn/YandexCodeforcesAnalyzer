"""Unit tests for the declined-solution marker (services.generation.solution_skip)."""
import pytest

from api.user.gpt.services.generation.solution_skip import _DEFAULT_REASON, parse_skip


@pytest.mark.parametrize("text", [
    "SKIP: no honest ML here",
    "skip - no honest ML here",
    # models copy the backticks the prompt puts around the marker
    "`SKIP: no honest ML here`",
    "**SKIP: no honest ML here**",
    "  \n`SKIP`: no honest ML here\n",
])
def test_skip_recognised(text):
    assert parse_skip(text) == "no honest ML here"


def test_skip_without_reason_gets_default():
    assert parse_skip("`SKIP`") == _DEFAULT_REASON


def test_skip_keeps_first_line_only():
    assert parse_skip("SKIP: short reason\nlong rambling explanation") == "short reason"


@pytest.mark.parametrize("code", [
    "#include <bits/stdc++.h>\nint main() {}",
    "import sys\nprint(sum(map(int, sys.stdin.read().split())))",
    "",
])
def test_real_code_is_not_a_skip(code):
    assert parse_skip(code) is None
