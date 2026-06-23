"""Unit tests for api/pydantic_schemas/user/codeforces.py — validators."""
import pytest
from pydantic import ValidationError

from api.pydantic_schemas.user.codeforces import (LinkCodeforces, Standings,
                                                  Submissions)


def test_link_codeforces_basic():
    m = LinkCodeforces(api_key="k", api_secret="s")
    assert m.api_key == "k" and m.api_secret == "s"


def test_standings_valid():
    m = Standings(
        contest_id=1, as_manager=False, from_pos=1, count=5, show_unofficial=True
    )
    assert m.from_pos == 1 and m.count == 5


@pytest.mark.parametrize("from_pos", [0, -1])
def test_standings_from_pos_must_be_positive(from_pos):
    with pytest.raises(ValidationError):
        Standings(
            contest_id=1, as_manager=False, from_pos=from_pos, count=5,
            show_unofficial=False,
        )


@pytest.mark.parametrize("count", [0, -3])
def test_standings_count_must_be_positive(count):
    with pytest.raises(ValidationError):
        Standings(
            contest_id=1, as_manager=False, from_pos=1, count=count,
            show_unofficial=False,
        )


def test_submissions_valid():
    m = Submissions(
        contest_id=1, as_manager=True, from_pos=2, count=10, include_source=True
    )
    assert m.include_source is True


def test_submissions_invalid_positions():
    with pytest.raises(ValidationError):
        Submissions(
            contest_id=1, as_manager=False, from_pos=0, count=1, include_source=False
        )
    with pytest.raises(ValidationError):
        Submissions(
            contest_id=1, as_manager=False, from_pos=1, count=0, include_source=False
        )
