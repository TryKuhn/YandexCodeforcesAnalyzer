"""Unit tests for api/user/merge_table.py.

``merge_table`` upserts a contest with its participants and per-task results.
It dedups against existing rows (matching by external_id / login / task_id),
reuses the global ``Participant`` record, and rolls back to a 500 on error.
"""
import pytest
from fastapi import HTTPException
from sqlalchemy import text

from api.user.merge_table import merge_table
from models import (
    Contest,
    ContestParticipant,
    Participant,
    Task,
    TaskResult,
)


def _new_contest(*, user_id, external_id=10, name="Contest A"):
    return Contest(
        user_id=user_id, platform="cf", external_id=external_id, name=name,
        type="ICPC", unofficial=False,
    )


async def _enable_fk(db):
    """SQLite ignores FK constraints unless explicitly enabled per-connection."""
    await db.execute(text("PRAGMA foreign_keys=ON"))


async def _seed_task(db, contest_id, task_id="t1"):
    task = Task(id=task_id, contest_id=contest_id, short_name="A",
                full_name="Apple", max_score=100)
    db.add(task)
    await db.flush()
    return task


@pytest.mark.asyncio
async def test_merge_table_inserts_new_contest(db, user):
    contest = _new_contest(user_id=user.id)
    db.add(contest)
    await db.flush()  # need a contest id for the FK on Task
    await _seed_task(db, contest.id)

    cp = ContestParticipant(login="alice", name="Alice", score=100.0)
    tr = TaskResult(task_id="t1", score=100.0, tries_count=1, verdict="OK")
    rows = [(cp, [tr])]

    result = await merge_table(contest, [], rows, user.id, db)
    assert result["message"] == "Standings updated successfully"
    assert result["contest_name"] == "Contest A"

    # Global participant created.
    parts = (await db.execute(
        Participant.__table__.select()
    )).fetchall()
    assert len(parts) == 1
    assert parts[0].login == "alice"

    # ContestParticipant + TaskResult persisted.
    cps = (await db.execute(ContestParticipant.__table__.select())).fetchall()
    assert len(cps) == 1
    trs = (await db.execute(TaskResult.__table__.select())).fetchall()
    assert len(trs) == 1
    assert trs[0].score == 100.0


@pytest.mark.asyncio
async def test_merge_table_reuses_existing_global_participant(db, user):
    # Pre-existing global participant with the same login.
    existing = Participant(user_id=user.id, login="alice", name="Old Name")
    db.add(existing)
    await db.flush()
    existing_id = existing.id

    contest = _new_contest(user_id=user.id, external_id=20)
    db.add(contest)
    await db.flush()
    await _seed_task(db, contest.id)

    cp = ContestParticipant(login="alice", name="Alice", score=50.0)
    tr = TaskResult(task_id="t1", score=50.0, tries_count=1, verdict="OK")
    await merge_table(contest, [], [(cp, [tr])], user.id, db)

    # No duplicate Participant; the existing one is reused.
    parts = (await db.execute(Participant.__table__.select())).fetchall()
    assert len(parts) == 1
    assert parts[0].id == existing_id


@pytest.mark.asyncio
async def test_merge_table_updates_existing_contest_rows(db, user):
    # First import.
    contest1 = _new_contest(user_id=user.id, external_id=30, name="Contest C")
    db.add(contest1)
    await db.flush()
    await _seed_task(db, contest1.id)
    cp1 = ContestParticipant(login="bob", name="Bob", score=10.0)
    tr1 = TaskResult(task_id="t1", score=10.0, tries_count=1, verdict="WA")
    await merge_table(contest1, [], [(cp1, [tr1])], user.id, db)

    # Second import for the SAME external contest with an updated score.
    contest2 = _new_contest(user_id=user.id, external_id=30, name="Contest C v2")
    cp2 = ContestParticipant(login="bob", name="Bob", score=99.0)
    tr2 = TaskResult(task_id="t1", score=99.0, tries_count=2, verdict="OK")
    result = await merge_table(contest2, [], [(cp2, [tr2])], user.id, db)
    assert result["contest_name"] == "Contest C v2"

    # Still a single contest / participant / task-result (updated in place).
    contests = (await db.execute(Contest.__table__.select())).fetchall()
    assert len(contests) == 1
    cps = (await db.execute(ContestParticipant.__table__.select())).fetchall()
    assert len(cps) == 1
    trs = (await db.execute(TaskResult.__table__.select())).fetchall()
    assert len(trs) == 1
    assert trs[0].score == 99.0
    assert trs[0].verdict == "OK"


@pytest.mark.asyncio
async def test_merge_table_rolls_back_and_raises_500_on_error(db, user):
    await _enable_fk(db)
    contest = _new_contest(user_id=user.id, external_id=40)
    db.add(contest)
    await db.flush()
    # No Task seeded → TaskResult FK (task_id="missing") violates integrity on commit.
    cp = ContestParticipant(login="carol", name="Carol", score=5.0)
    tr = TaskResult(task_id="missing-task", score=5.0, tries_count=1, verdict="OK")

    with pytest.raises(HTTPException) as exc:
        await merge_table(contest, [], [(cp, [tr])], user.id, db)
    assert exc.value.status_code == 500
