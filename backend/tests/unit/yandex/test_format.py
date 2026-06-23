"""Unit tests for api/user/yandex/format.py — standings/submissions formatting."""
from datetime import datetime, timedelta

import pytest

from api.user.yandex.format import (format_yandex_standings,
                                     format_yandex_submissions)
from models import (Contest, ContestParticipant, Participant, Submission,
                    Task, TaskResult)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _contest(plugin="acm", start="2026-01-01T10:00:00.000Z", duration=7200, cid=100):
    c = {
        "id": cid,
        "name": "Round 1",
        "standingsPlugin": plugin,
        "duration": duration,
    }
    if start is not None:
        c["startTime"] = start
    return c


def _titles():
    return [
        {"id": "p1", "title": "A", "name": "Apple"},
        {"id": "p2", "title": "B", "name": "Banana"},
    ]


def _standings(rows, titles=None):
    return {"titles": titles if titles is not None else _titles(), "rows": rows}


def _row(login, name, results):
    """results: list of dicts merged onto a default problemResult."""
    pr = []
    for r in results:
        base = {"status": "NOT_SUBMITTED", "score": "", "submissionCount": 1}
        base.update(r)
        pr.append(base)
    return {
        "participantInfo": {"login": login, "name": name},
        "problemResults": pr,
    }


# --------------------------------------------------------------------------- #
# contest / tasks construction
# --------------------------------------------------------------------------- #
def test_basic_contest_and_tasks_acm_icpc():
    rows = [
        _row("alice", "Alice", [
            {"status": "ACCEPTED", "score": "", "submissionCount": 1, "submitDelay": 60},
            {"status": "NOT_SUBMITTED", "score": "", "submissionCount": 1},
        ]),
    ]
    contest, tasks, formatted_rows = format_yandex_standings(
        _contest(), _standings(rows), user_id=5, unofficial=False
    )

    assert isinstance(contest, Contest)
    assert contest.external_id == 100
    assert contest.user_id == 5
    assert contest.platform == "yandex"
    assert contest.type == "ICPC"  # standingsPlugin == "acm"
    assert contest.unofficial is False
    assert contest.duration == timedelta(seconds=7200)
    # startTime parsed, tz stripped
    assert contest.start_time == datetime(2026, 1, 1, 10, 0, 0)

    assert len(tasks) == 2
    assert all(isinstance(t, Task) for t in tasks)
    assert tasks[0].id == "ya_5_100_p1"
    assert tasks[0].short_name == "A"
    assert tasks[0].full_name == "Apple"
    assert tasks[1].id == "ya_5_100_p2"

    assert len(formatted_rows) == 1
    cp, results = formatted_rows[0]
    assert isinstance(cp, ContestParticipant)
    assert cp.login == "alice"
    assert cp.name == "Alice"


def test_contest_type_ioi_when_plugin_not_acm():
    contest, _, _ = format_yandex_standings(
        _contest(plugin="default"), _standings([]), user_id=1, unofficial=False
    )
    assert contest.type == "IOI"


def test_unofficial_flag_propagated():
    contest, _, _ = format_yandex_standings(
        _contest(), _standings([]), user_id=1, unofficial=True
    )
    assert contest.unofficial is True


def test_missing_start_time_is_none():
    contest, _, formatted_rows = format_yandex_standings(
        _contest(start=None),
        _standings([_row("a", "A", [{"status": "ACCEPTED", "submitDelay": 30}, {}])]),
        user_id=1,
        unofficial=False,
    )
    assert contest.start_time is None


def test_invalid_start_time_falls_back_to_none():
    contest, _, _ = format_yandex_standings(
        _contest(start="not-a-date"), _standings([]), user_id=1, unofficial=False
    )
    assert contest.start_time is None


def test_missing_duration_defaults_to_zero():
    c = _contest()
    del c["duration"]
    contest, _, _ = format_yandex_standings(
        c, _standings([]), user_id=1, unofficial=False
    )
    assert contest.duration == timedelta(seconds=0)


def test_no_titles_yields_no_tasks():
    _, tasks, _ = format_yandex_standings(
        _contest(), _standings([], titles=[]), user_id=1, unofficial=False
    )
    assert tasks == []


# --------------------------------------------------------------------------- #
# scoring: best_scores / max_score
# --------------------------------------------------------------------------- #
def test_max_score_from_accepted_status_when_score_empty():
    # ICPC-style: empty score string -> 1.0 if ACCEPTED else 0.0
    rows = [_row("a", "A", [{"status": "ACCEPTED", "score": ""}, {"status": "NOT_SUBMITTED", "score": ""}])]
    _, tasks, _ = format_yandex_standings(
        _contest(), _standings(rows), user_id=1, unofficial=False
    )
    assert tasks[0].max_score == 1.0
    assert tasks[1].max_score == 0.0


def test_max_score_from_numeric_score_string():
    rows = [
        _row("a", "A", [{"score": "30"}, {"score": "0"}]),
        _row("b", "B", [{"score": "55"}, {"score": "100"}]),
    ]
    _, tasks, _ = format_yandex_standings(
        _contest(plugin="ioi"), _standings(rows), user_id=1, unofficial=False
    )
    assert tasks[0].max_score == 55.0   # best of 30 / 55
    assert tasks[1].max_score == 100.0  # best of 0 / 100


# --------------------------------------------------------------------------- #
# tries / submissionCount
# --------------------------------------------------------------------------- #
def test_tries_count_is_submission_count_minus_one():
    rows = [_row("a", "A", [{"status": "NOT_SUBMITTED", "score": "", "submissionCount": 4}, {}])]
    _, _, formatted_rows = format_yandex_standings(
        _contest(), _standings(rows), user_id=1, unofficial=False
    )
    _, results = formatted_rows[0]
    a_res = next(r for r in results if r.task_id == "ya_1_100_p1")
    assert a_res.tries_count == 3
    assert a_res.verdict == "WA"  # 0 points, >0 tries


def test_default_submission_count_when_absent():
    # default submissionCount=1 -> tries == 0
    rows = [_row("a", "A", [{"status": "ACCEPTED", "score": ""}, {}])]
    _, _, formatted_rows = format_yandex_standings(
        _contest(), _standings(rows), user_id=1, unofficial=False
    )
    _, results = formatted_rows[0]
    a_res = next(r for r in results if r.task_id == "ya_1_100_p1")
    assert a_res.tries_count == 0


# --------------------------------------------------------------------------- #
# verdict branches OK / PARTIAL / WA / NULL
# --------------------------------------------------------------------------- #
def test_verdicts_ok_partial_wa_null():
    # Task B max becomes 80 (bob), so alice's 50 on B -> PARTIAL.
    rows = [
        _row("alice", "Alice", [
            {"status": "ACCEPTED", "score": "", "submitDelay": 60},     # A=1.0 OK
            {"score": "50", "submitDelay": 120},                        # B=50 PARTIAL
        ]),
        _row("bob", "Bob", [
            {"status": "NOT_SUBMITTED", "score": "", "submissionCount": 4},  # A=0, 3 tries WA
            {"score": "80", "submitDelay": 90},                              # B=80 sets max
        ]),
    ]
    _, tasks, formatted_rows = format_yandex_standings(
        _contest(), _standings(rows), user_id=1, unofficial=False
    )
    by_login = {cp.login: results for cp, results in formatted_rows}

    alice = {r.task_id: r.verdict for r in by_login["alice"]}
    assert alice["ya_1_100_p1"] == "OK"       # 1.0 == max 1.0
    assert alice["ya_1_100_p2"] == "PARTIAL"  # 50 < 80

    bob = {r.task_id: r.verdict for r in by_login["bob"]}
    assert bob["ya_1_100_p1"] == "WA"   # 0 points, 3 tries
    assert bob["ya_1_100_p2"] == "OK"   # 80 == max 80


def test_verdict_null_when_zero_score_zero_tries():
    rows = [_row("a", "A", [{"status": "NOT_SUBMITTED", "score": "", "submissionCount": 1}, {}])]
    _, _, formatted_rows = format_yandex_standings(
        _contest(), _standings(rows), user_id=1, unofficial=False
    )
    _, results = formatted_rows[0]
    a_res = next(r for r in results if r.task_id == "ya_1_100_p1")
    assert a_res.verdict == "NULL"


# --------------------------------------------------------------------------- #
# success time
# --------------------------------------------------------------------------- #
def test_success_time_computed_from_submit_delay():
    rows = [_row("a", "A", [{"status": "ACCEPTED", "score": "", "submitDelay": 300}, {}])]
    _, _, formatted_rows = format_yandex_standings(
        _contest(), _standings(rows), user_id=1, unofficial=False
    )
    _, results = formatted_rows[0]
    a_res = next(r for r in results if r.task_id == "ya_1_100_p1")
    assert a_res.last_success_time == datetime(2026, 1, 1, 10, 0, 0) + timedelta(seconds=300)


def test_success_time_none_without_start_time():
    rows = [_row("a", "A", [{"status": "ACCEPTED", "score": "", "submitDelay": 300}, {}])]
    _, _, formatted_rows = format_yandex_standings(
        _contest(start=None), _standings(rows), user_id=1, unofficial=False
    )
    _, results = formatted_rows[0]
    a_res = next(r for r in results if r.task_id == "ya_1_100_p1")
    assert a_res.last_success_time is None


def test_success_time_none_when_no_submit_delay():
    rows = [_row("a", "A", [{"status": "ACCEPTED", "score": ""}, {}])]
    _, _, formatted_rows = format_yandex_standings(
        _contest(), _standings(rows), user_id=1, unofficial=False
    )
    _, results = formatted_rows[0]
    a_res = next(r for r in results if r.task_id == "ya_1_100_p1")
    assert a_res.last_success_time is None


# --------------------------------------------------------------------------- #
# participant total score
# --------------------------------------------------------------------------- #
def test_participant_total_score():
    rows = [_row("a", "A", [{"score": "30", "submitDelay": 1}, {"score": "70", "submitDelay": 1}])]
    _, _, formatted_rows = format_yandex_standings(
        _contest(plugin="ioi"), _standings(rows), user_id=1, unofficial=False
    )
    cp, _ = formatted_rows[0]
    assert cp.score == 100.0


# --------------------------------------------------------------------------- #
# merge / dedup of duplicate participant rows
# --------------------------------------------------------------------------- #
def test_merge_duplicate_rows_keeps_best_score_and_accumulates_tries():
    rows = [
        _row("alice", "Alice", [
            {"score": "40", "submissionCount": 2, "submitDelay": 100},  # 1 try
            {"status": "NOT_SUBMITTED", "score": "", "submissionCount": 1},
        ]),
        _row("alice", "Alice", [
            {"score": "100", "submissionCount": 3, "submitDelay": 50},  # 2 tries
            {"status": "NOT_SUBMITTED", "score": "", "submissionCount": 1},
        ]),
    ]
    _, _, formatted_rows = format_yandex_standings(
        _contest(plugin="ioi"), _standings(rows), user_id=1, unofficial=False
    )
    assert len(formatted_rows) == 1
    _, results = formatted_rows[0]
    a_res = next(r for r in results if r.task_id == "ya_1_100_p1")
    assert a_res.score == 100.0
    assert a_res.tries_count == 3  # 1 + 2 accumulated
    # success_time from the higher score row (delay 50)
    assert a_res.last_success_time == datetime(2026, 1, 1, 10, 0, 0) + timedelta(seconds=50)


def test_merge_equal_score_keeps_earlier_success_time():
    rows = [
        _row("alice", "Alice", [{"score": "50", "submitDelay": 200}, {}]),
        _row("alice", "Alice", [{"score": "50", "submitDelay": 100}, {}]),
    ]
    _, _, formatted_rows = format_yandex_standings(
        _contest(plugin="ioi"), _standings(rows), user_id=1, unofficial=False
    )
    _, results = formatted_rows[0]
    a_res = next(r for r in results if r.task_id == "ya_1_100_p1")
    assert a_res.score == 50.0
    # earlier (smaller delay) success time wins
    assert a_res.last_success_time == datetime(2026, 1, 1, 10, 0, 0) + timedelta(seconds=100)


def test_merge_equal_score_does_not_replace_with_later_time():
    rows = [
        _row("alice", "Alice", [{"score": "50", "submitDelay": 100}, {}]),
        _row("alice", "Alice", [{"score": "50", "submitDelay": 300}, {}]),
    ]
    _, _, formatted_rows = format_yandex_standings(
        _contest(plugin="ioi"), _standings(rows), user_id=1, unofficial=False
    )
    _, results = formatted_rows[0]
    a_res = next(r for r in results if r.task_id == "ya_1_100_p1")
    assert a_res.last_success_time == datetime(2026, 1, 1, 10, 0, 0) + timedelta(seconds=100)


def test_row_with_fewer_results_than_titles_skips_missing_problem():
    # Two titles but the row only carries ONE problemResult -> the second
    # problem has no merged result for this login and is skipped (continue).
    rows = [_row("alice", "Alice", [{"score": "10", "submitDelay": 1}])]
    _, _, formatted_rows = format_yandex_standings(
        _contest(plugin="ioi"), _standings(rows), user_id=1, unofficial=False
    )
    _, results = formatted_rows[0]
    task_ids = {r.task_id for r in results}
    assert task_ids == {"ya_1_100_p1"}  # p2 skipped, only p1 present


def test_distinct_logins_create_distinct_participants():
    rows = [
        _row("alice", "Alice", [{"score": "10"}, {}]),
        _row("bob", "Bob", [{"score": "20"}, {}]),
    ]
    _, _, formatted_rows = format_yandex_standings(
        _contest(plugin="ioi"), _standings(rows), user_id=1, unofficial=False
    )
    logins = sorted(cp.login for cp, _ in formatted_rows)
    assert logins == ["alice", "bob"]


# --------------------------------------------------------------------------- #
# format_yandex_submissions (DB-driven)
# --------------------------------------------------------------------------- #
async def _seed(db, user, *, contest_id, external_id, short_name="A",
                full_name="Apple", pname="Alice", login="alice"):
    contest = Contest(
        id=contest_id, user_id=user.id, platform="yandex", external_id=external_id,
        name="C", type="ICPC", unofficial=False,
    )
    db.add(contest)
    await db.flush()
    part = Participant(id=contest_id, user_id=user.id, login=login, name=pname)
    db.add(part)
    await db.flush()
    task = Task(id=f"ya_t{contest_id}", contest_id=contest_id, short_name=short_name,
                full_name=full_name, max_score=100)
    cp = ContestParticipant(id=contest_id, contest_id=contest_id, participant_id=contest_id,
                            login=login, name=pname, score=0.0)
    db.add_all([task, cp])
    await db.flush()
    tr = TaskResult(id=contest_id, contest_participant_id=contest_id, task_id=task.id,
                    score=100, tries_count=0, verdict="OK")
    db.add(tr)
    await db.commit()
    return task, cp, tr


def _submission(**over):
    base = {
        "id": 999,
        "problemAlias": "A",
        "author": "Alice",
        "submissionTime": "2026-01-01T10:05:00.000Z",
        "compiler": "g++",
        "score": "",
        "verdict": "ACCEPTED",
        "time": 200,
        "memory": 1048576,
        "source": "code",
    }
    base.update(over)
    return base


@pytest.mark.asyncio
async def test_format_submissions_matches_db_records(db, user):
    task, cp, tr = await _seed(db, user, contest_id=1, external_id=100)

    result = await format_yandex_submissions(
        (_submission(),), user_id=user.id, contest_id=1, db=db
    )
    assert len(result) == 1
    sub = result[0]
    assert isinstance(sub, Submission)
    assert sub.id == f"yandex_{user.id}_1_999"
    assert sub.contest_id == 1
    assert sub.task_result_id == tr.id
    assert sub.participant_login == "alice"
    assert sub.task_name == "Apple"
    assert sub.language == "g++"
    assert sub.verdict == "ACCEPTED"
    assert sub.send_time == datetime(2026, 1, 1, 10, 5, 0)
    assert sub.run_time == timedelta(milliseconds=200)
    assert sub.memory_bytes == 1048576
    # ACCEPTED with empty score -> 1.0
    assert sub.score == 1.0
    # source base64-encoded
    from base64 import b64encode
    assert sub.source == b64encode(b"code").decode("utf-8")


@pytest.mark.asyncio
async def test_format_submissions_numeric_score(db, user):
    await _seed(db, user, contest_id=2, external_id=200)
    result = await format_yandex_submissions(
        (_submission(score="73", verdict="PARTIAL"),),
        user_id=user.id, contest_id=2, db=db,
    )
    assert result[0].score == 73.0


@pytest.mark.asyncio
async def test_format_submissions_none_score_treated_as_status(db, user):
    await _seed(db, user, contest_id=3, external_id=300)
    result = await format_yandex_submissions(
        (_submission(score=None, verdict="WRONG_ANSWER"),),
        user_id=user.id, contest_id=3, db=db,
    )
    # non-accepted + None score -> 0.0
    assert result[0].score == 0.0


@pytest.mark.asyncio
async def test_format_submissions_skips_unknown_problem(db, user):
    await _seed(db, user, contest_id=4, external_id=400, short_name="A")
    result = await format_yandex_submissions(
        (_submission(problemAlias="ZZZ"),), user_id=user.id, contest_id=4, db=db
    )
    assert result == []


@pytest.mark.asyncio
async def test_format_submissions_skips_unknown_participant(db, user):
    await _seed(db, user, contest_id=5, external_id=500, pname="Alice")
    result = await format_yandex_submissions(
        (_submission(author="Ghost"),), user_id=user.id, contest_id=5, db=db
    )
    assert result == []


@pytest.mark.asyncio
async def test_format_submissions_skips_when_no_task_result(db, user):
    # Seed contest + task + participant but NO task_result.
    contest = Contest(
        id=6, user_id=user.id, platform="yandex", external_id=600,
        name="C", type="ICPC", unofficial=False,
    )
    db.add(contest)
    await db.flush()
    part = Participant(id=6, user_id=user.id, login="alice", name="Alice")
    db.add(part)
    await db.flush()
    task = Task(id="ya_t6", contest_id=6, short_name="A", full_name="Apple", max_score=100)
    cp = ContestParticipant(id=6, contest_id=6, participant_id=6, login="alice",
                            name="Alice", score=0.0)
    db.add_all([task, cp])
    await db.commit()

    result = await format_yandex_submissions(
        (_submission(),), user_id=user.id, contest_id=6, db=db
    )
    assert result == []


@pytest.mark.asyncio
async def test_format_submissions_empty_input(db, user):
    result = await format_yandex_submissions((), user_id=user.id, contest_id=1, db=db)
    assert result == []


@pytest.mark.asyncio
async def test_format_submissions_multiple_mixed(db, user):
    await _seed(db, user, contest_id=7, external_id=700)
    subs = (
        _submission(id=1, score="10"),
        _submission(id=2, problemAlias="ZZZ"),  # skipped (unknown problem)
        _submission(id=3, author="Ghost"),       # skipped (unknown participant)
        _submission(id=4, score="20"),
    )
    result = await format_yandex_submissions(
        subs, user_id=user.id, contest_id=7, db=db
    )
    ids = sorted(s.id for s in result)
    assert ids == [f"yandex_{user.id}_7_1", f"yandex_{user.id}_7_4"]
