"""Unit tests for api/user/codeforces/format.py — standings/submissions formatting."""
from datetime import datetime, timedelta

import pytest

from api.user.codeforces.format import (format_codeforces_standings,
                                        format_codeforces_submissions)
from models import (Contest, ContestParticipant, Participant, Submission,
                    Task, TaskResult)


def _standings(rows, problems=None, contest=None):
    return {
        "contest": contest
        or {
            "id": 100,
            "name": "Round 1",
            "type": "ICPC",
            "durationSeconds": 7200,
            "startTimeSeconds": int(datetime(2026, 1, 1).timestamp()),
        },
        "problems": problems
        or [
            {"index": "A", "name": "Apple"},
            {"index": "B", "name": "Banana"},
        ],
        "rows": rows,
    }


def test_standings_basic_contest_and_tasks():
    rows = [
        {
            "party": {"members": [{"handle": "alice", "name": "Alice"}]},
            "problemResults": [
                {"points": 100, "rejectedAttemptCount": 0, "bestSubmissionTimeSeconds": 60},
                {"points": 0, "rejectedAttemptCount": 2},
            ],
        }
    ]
    contest, tasks, formatted_rows = format_codeforces_standings(
        _standings(rows), user_id=5, unofficial=False
    )

    assert isinstance(contest, Contest)
    assert contest.external_id == 100
    assert contest.user_id == 5
    assert contest.platform == "cf"
    assert contest.unofficial is False
    assert contest.duration == timedelta(seconds=7200)
    assert contest.start_time == datetime.fromtimestamp(
        int(datetime(2026, 1, 1).timestamp())
    )

    assert len(tasks) == 2
    assert all(isinstance(t, Task) for t in tasks)
    assert tasks[0].id == "cf_5_100_A"
    assert tasks[0].short_name == "A"
    assert tasks[0].full_name == "Apple"

    # one participant row
    assert len(formatted_rows) == 1
    cp, results = formatted_rows[0]
    assert isinstance(cp, ContestParticipant)
    assert cp.login == "alice"
    assert cp.name == "Alice"


def test_standings_verdicts_ok_partial_wa_null():
    # Task max_score is derived from the BEST score across all rows (problems
    # carry no "points"). Bob scores 80 on B, so B's max becomes 80 and alice's
    # 50 < 80 -> PARTIAL. Alice's A=100 is the best on A -> OK.
    rows = [
        {  # alice: A=100 (OK), B=50 (PARTIAL since best on B is 80)
            "party": {"members": [{"handle": "alice"}]},
            "problemResults": [
                {"points": 100, "rejectedAttemptCount": 0, "bestSubmissionTimeSeconds": 60},
                {"points": 50, "rejectedAttemptCount": 0, "bestSubmissionTimeSeconds": 120},
            ],
        },
        {  # bob: A=0 with 3 tries (WA), B=80 (sets the B max)
            "party": {"members": [{"handle": "bob"}]},
            "problemResults": [
                {"points": 0, "rejectedAttemptCount": 3},
                {"points": 80, "rejectedAttemptCount": 0, "bestSubmissionTimeSeconds": 90},
            ],
        },
    ]
    _, tasks, formatted_rows = format_codeforces_standings(
        _standings(rows), user_id=1, unofficial=True
    )
    by_login = {cp.login: results for cp, results in formatted_rows}

    alice_verdicts = {r.task_id: r.verdict for r in by_login["alice"]}
    assert alice_verdicts["cf_1_100_A"] == "OK"
    assert alice_verdicts["cf_1_100_B"] == "PARTIAL"

    bob_verdicts = {r.task_id: r.verdict for r in by_login["bob"]}
    assert bob_verdicts["cf_1_100_A"] == "WA"   # 0 points but 3 tries
    assert bob_verdicts["cf_1_100_B"] == "OK"   # 80 == B's max (80)


def test_standings_participant_total_score():
    rows = [
        {
            "party": {"members": [{"handle": "alice"}]},
            "problemResults": [
                {"points": 100, "rejectedAttemptCount": 0, "bestSubmissionTimeSeconds": 1},
                {"points": 30, "rejectedAttemptCount": 0, "bestSubmissionTimeSeconds": 1},
            ],
        }
    ]
    _, _, formatted_rows = format_codeforces_standings(
        _standings(rows), user_id=1, unofficial=False
    )
    cp, _ = formatted_rows[0]
    assert cp.score == 130.0


def test_standings_team_login_and_name():
    rows = [
        {
            "party": {"teamId": 77, "teamName": "Dream Team", "members": [{"handle": "x"}]},
            "problemResults": [
                {"points": 0, "rejectedAttemptCount": 0},
                {"points": 0, "rejectedAttemptCount": 0},
            ],
        }
    ]
    _, _, formatted_rows = format_codeforces_standings(
        _standings(rows), user_id=2, unofficial=False
    )
    cp, _ = formatted_rows[0]
    assert cp.login == "team_77"
    assert cp.name == "Dream Team"


def test_standings_type_cf_remapped_to_icpc():
    contest = {
        "id": 9,
        "name": "C",
        "type": "CF",
        "durationSeconds": 60,
    }
    _, _, _ = format_codeforces_standings(
        _standings([], contest=contest), user_id=1, unofficial=False
    )
    c, _, _ = format_codeforces_standings(
        _standings([], contest=contest), user_id=1, unofficial=False
    )
    assert c.type == "ICPC"
    # start_time is None when startTimeSeconds is absent
    assert c.start_time is None


def test_standings_merges_duplicate_rows_takes_best_score():
    # Same participant appears twice (e.g. official + unofficial merge): keep max.
    rows = [
        {
            "party": {"members": [{"handle": "alice"}]},
            "problemResults": [
                {"points": 40, "rejectedAttemptCount": 1, "bestSubmissionTimeSeconds": 100},
                {"points": 0, "rejectedAttemptCount": 0},
            ],
        },
        {
            "party": {"members": [{"handle": "alice"}]},
            "problemResults": [
                {"points": 100, "rejectedAttemptCount": 2, "bestSubmissionTimeSeconds": 50},
                {"points": 0, "rejectedAttemptCount": 0},
            ],
        },
    ]
    _, _, formatted_rows = format_codeforces_standings(
        _standings(rows), user_id=1, unofficial=False
    )
    assert len(formatted_rows) == 1
    cp, results = formatted_rows[0]
    a_res = next(r for r in results if r.task_id == "cf_1_100_A")
    assert a_res.score == 100.0
    # tries accumulate across both rows
    assert a_res.tries_count == 3
    # Task B had 0 points and 0 tries on both rows -> NULL verdict.
    b_res = next(r for r in results if r.task_id == "cf_1_100_B")
    assert b_res.verdict == "NULL"


@pytest.mark.asyncio
async def test_format_submissions_matches_db_records(db, user):
    # Build a contest + task + participant + task_result so format can resolve FKs.
    contest = Contest(
        id=1, user_id=user.id, platform="cf", external_id=100,
        name="C", type="ICPC", unofficial=False,
    )
    db.add(contest)
    await db.flush()
    part = Participant(id=1, user_id=user.id, login="alice", name="A")
    db.add(part)
    await db.flush()
    task = Task(id="cf_t1", contest_id=1, short_name="A", full_name="Apple", max_score=100)
    cp = ContestParticipant(id=1, contest_id=1, participant_id=1, login="alice", name="A", score=0.0)
    db.add_all([task, cp])
    await db.flush()
    tr = TaskResult(
        id=1, contest_participant_id=1, task_id="cf_t1", score=100,
        tries_count=0, verdict="OK",
    )
    db.add(tr)
    await db.commit()

    submissions = [
        {
            "id": 999,
            "problem": {"name": "Apple"},
            "author": {"members": [{"handle": "alice"}]},
            "creationTimeSeconds": int(datetime(2026, 1, 1).timestamp()),
            "programmingLanguage": "GNU C++17",
            "points": 100,
            "verdict": "OK",
            "timeConsumedMillis": 200,
            "memoryConsumedBytes": 1024,
            "sourceBase64": "Y29kZQ==",
        }
    ]
    result = await format_codeforces_submissions(
        submissions, user_id=user.id, contest_id=1, db=db
    )
    assert len(result) == 1
    sub = result[0]
    assert isinstance(sub, Submission)
    assert sub.id == f"cf_{user.id}_1_999"
    assert sub.participant_login == "alice"
    assert sub.task_name == "Apple"
    assert sub.verdict == "OK"
    assert sub.run_time == timedelta(milliseconds=200)
    assert sub.memory_bytes == 1024
    assert sub.source == "Y29kZQ=="


@pytest.mark.asyncio
async def test_format_submissions_skips_unknown_participant(db, user):
    contest = Contest(
        id=2, user_id=user.id, platform="cf", external_id=200,
        name="C", type="ICPC", unofficial=False,
    )
    db.add(contest)
    await db.flush()
    task = Task(id="cf_t2", contest_id=2, short_name="A", full_name="Apple", max_score=100)
    db.add(task)
    await db.commit()

    submissions = [
        {
            "id": 1,
            "problem": {"name": "Apple"},
            "author": {"members": [{"handle": "ghost"}]},
            "creationTimeSeconds": 0,
            "programmingLanguage": "Python",
            "verdict": "OK",
            "timeConsumedMillis": 1,
            "memoryConsumedBytes": 1,
            "sourceBase64": "x",
        }
    ]
    # No participant "ghost" exists -> submission skipped.
    result = await format_codeforces_submissions(
        submissions, user_id=user.id, contest_id=2, db=db
    )
    assert result == []
