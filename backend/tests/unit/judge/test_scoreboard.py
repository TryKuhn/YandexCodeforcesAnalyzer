"""ICPC and IOI standings."""
from api.judge.scoreboard import (PENALTY_MINUTES, SubmissionFact, build_rows,
                                  places)

ICPC = "icpc"
IOI = "ioi"

PARTICIPANTS = {
    1: ("alice", True),
    2: ("bob", True),
}


def _fact(user_id, problem_id, verdict, minute, score=0.0) -> SubmissionFact:
    return SubmissionFact(
        user_id=user_id, problem_id=problem_id, verdict=verdict, minute=minute, score=score
    )


def test_icpc_counts_solved_problems():
    rows = build_rows(
        [_fact(1, 10, "OK", 5), _fact(1, 11, "OK", 30)], PARTICIPANTS, ICPC
    )
    assert rows[0].user_id == 1
    assert rows[0].solved == 2


def test_icpc_penalty_is_time_plus_failed_attempts():
    rows = build_rows(
        [_fact(1, 10, "WA", 5), _fact(1, 10, "WA", 8), _fact(1, 10, "OK", 20)],
        PARTICIPANTS,
        ICPC,
    )
    # solved at minute 20 after two failures
    assert rows[0].penalty == 20 + 2 * PENALTY_MINUTES


def test_icpc_failures_after_solving_are_free():
    rows = build_rows(
        [_fact(1, 10, "OK", 10), _fact(1, 10, "WA", 15)], PARTICIPANTS, ICPC
    )
    assert rows[0].penalty == 10


def test_icpc_unsolved_problem_adds_no_penalty():
    rows = build_rows([_fact(1, 10, "WA", 5), _fact(1, 10, "TLE", 9)], PARTICIPANTS, ICPC)
    assert rows[0].solved == 0
    assert rows[0].penalty == 0


def test_icpc_compile_error_is_not_an_attempt():
    rows = build_rows(
        [_fact(1, 10, "CE", 3), _fact(1, 10, "OK", 10)], PARTICIPANTS, ICPC
    )
    assert rows[0].penalty == 10


def test_icpc_more_solved_beats_lower_penalty():
    rows = build_rows(
        [
            _fact(1, 10, "OK", 100),
            _fact(1, 11, "OK", 110),
            _fact(2, 10, "OK", 1),
        ],
        PARTICIPANTS,
        ICPC,
    )
    assert [r.user_id for r in rows] == [1, 2]


def test_icpc_penalty_breaks_a_tie_on_solved():
    rows = build_rows(
        [_fact(1, 10, "OK", 50), _fact(2, 10, "OK", 5)], PARTICIPANTS, ICPC
    )
    assert [r.user_id for r in rows] == [2, 1]


def test_ioi_sums_the_best_score_per_problem():
    rows = build_rows(
        [
            _fact(1, 10, "WA", 5, score=30),
            _fact(1, 10, "WA", 9, score=70),
            _fact(1, 11, "OK", 12, score=100),
        ],
        PARTICIPANTS,
        IOI,
    )
    assert rows[0].score == 170


def test_ioi_later_worse_attempt_does_not_lower_the_score():
    rows = build_rows(
        [_fact(1, 10, "OK", 5, score=100), _fact(1, 10, "WA", 30, score=0)],
        PARTICIPANTS,
        IOI,
    )
    assert rows[0].score == 100


def test_ioi_ignores_penalty_entirely():
    rows = build_rows(
        [
            _fact(1, 10, "WA", 200, score=90),
            _fact(2, 10, "OK", 1, score=80),
        ],
        PARTICIPANTS,
        IOI,
    )
    assert [r.user_id for r in rows] == [1, 2]


def test_submissions_from_strangers_are_ignored():
    rows = build_rows([_fact(99, 10, "OK", 5)], PARTICIPANTS, ICPC)
    assert all(row.solved == 0 for row in rows)


def test_places_share_a_number_on_a_tie():
    rows = build_rows(
        [_fact(1, 10, "OK", 10), _fact(2, 10, "OK", 10)], PARTICIPANTS, ICPC
    )
    assert places(rows, ICPC) == [1, 1]


def test_places_count_upwards_when_results_differ():
    rows = build_rows(
        [_fact(1, 10, "OK", 5), _fact(2, 10, "OK", 40)], PARTICIPANTS, ICPC
    )
    assert places(rows, ICPC) == [1, 2]


def test_unofficial_participants_are_listed_but_not_placed():
    participants = {1: ("alice", True), 2: ("guest", False)}
    rows = build_rows(
        [_fact(2, 10, "OK", 1), _fact(1, 10, "OK", 50)], participants, ICPC
    )
    assigned = places(rows, ICPC)
    guest_index = next(i for i, r in enumerate(rows) if r.user_id == 2)
    alice_index = next(i for i, r in enumerate(rows) if r.user_id == 1)
    assert assigned[guest_index] == 0
    assert assigned[alice_index] == 1


def test_empty_contest_yields_a_row_per_participant():
    rows = build_rows([], PARTICIPANTS, ICPC)
    assert len(rows) == 2
    assert all(row.solved == 0 for row in rows)
