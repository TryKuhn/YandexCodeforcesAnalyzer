"""Unit tests for build pipeline pure helpers (services.build.pipeline)."""
from api.user.gpt.services.build.pipeline import _format_range


def test_format_range_contiguous():
    assert _format_range([1, 2, 3]) == "1-3"


def test_format_range_with_gaps():
    assert _format_range([1, 2, 3, 5, 7, 8]) == "1-3, 5, 7-8"


def test_format_range_single():
    assert _format_range([7]) == "7"


def test_format_range_empty():
    assert _format_range([]) == "—"


def test_format_range_unsorted_input():
    assert _format_range([3, 1, 2]) == "1-3"
