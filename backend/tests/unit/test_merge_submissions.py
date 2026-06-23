"""Unit tests for api/user/merge_submissions.py.

``merge_submissions`` upserts a batch of Submission rows and commits, or rolls
back and raises a 500 on any failure.
"""
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text

from api.user.merge_submissions import merge_submissions
from models import (
    Contest,
    ContestParticipant,
    Participant,
    Submission,
    Task,
    TaskResult,
)


async def _seed_chain(db, user):
    """Create the FK chain a Submission depends on: contest, task, cp, task_result."""
    contest = Contest(id=1, user_id=user.id, platform="cf", external_id=1,
                      name="C", type="ICPC", unofficial=False)
    db.add(contest)
    await db.flush()
    part = Participant(id=1, user_id=user.id, login="alice", name="Alice")
    db.add(part)
    await db.flush()
    cp = ContestParticipant(id=1, contest_id=1, participant_id=1,
                            login="alice", name="Alice", score=0.0)
    task = Task(id="t1", contest_id=1, short_name="A", full_name="Apple",
                max_score=100)
    db.add_all([cp, task])
    await db.flush()
    tr = TaskResult(id=1, contest_participant_id=1, task_id="t1", score=0.0,
                    tries_count=0, verdict="OK")
    db.add(tr)
    await db.flush()


def _make_submission(sub_id):
    return Submission(
        id=sub_id, contest_id=1, task_result_id=1, participant_login="alice",
        task_name="Apple", send_time=datetime(2026, 1, 1), language="GNU C++17",
        score=100.0, verdict="OK", run_time=timedelta(milliseconds=1),
        memory_bytes=1, banned=False, source="x",
    )


@pytest.mark.asyncio
async def test_merge_submissions_inserts(db, user):
    await _seed_chain(db, user)
    await db.commit()

    subs = [_make_submission("a"), _make_submission("b")]
    await merge_submissions(subs, db)

    rows = (await db.execute(select(Submission))).scalars().all()
    assert {r.id for r in rows} == {"a", "b"}


@pytest.mark.asyncio
async def test_merge_submissions_upserts_existing(db, user):
    await _seed_chain(db, user)
    db.add(_make_submission("a"))
    await db.commit()

    updated = _make_submission("a")
    updated.verdict = "WA"
    updated.score = 0.0
    await merge_submissions([updated], db)

    rows = (await db.execute(select(Submission))).scalars().all()
    assert len(rows) == 1
    assert rows[0].verdict == "WA"


@pytest.mark.asyncio
async def test_merge_submissions_empty_list_commits(db, user):
    # No submissions → should simply commit without error.
    await merge_submissions([], db)


@pytest.mark.asyncio
async def test_merge_submissions_rolls_back_and_raises_500(db, user):
    # SQLite ignores FK constraints unless explicitly enabled per-connection.
    await db.execute(text("PRAGMA foreign_keys=ON"))
    await _seed_chain(db, user)
    await db.commit()

    # task_result_id=999 violates the FK → merge/commit fails → HTTP 500.
    bad = _make_submission("c")
    bad.task_result_id = 999
    with pytest.raises(HTTPException) as exc:
        await merge_submissions([bad], db)
    assert exc.value.status_code == 500
