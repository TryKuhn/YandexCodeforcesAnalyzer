"""Unit tests for models/plagiarism/plagiarism_report.py (the active model).

The duplicate class in models/submissions/plagiarism_report.py shares the same
__tablename__ and cannot be imported once this one is registered, so only the
active model is exercised here.
"""
from datetime import datetime, timedelta

import pytest

from models import (Contest, ContestParticipant, PairOfBannedSubmissions,
                    Participant, PlagiarismReport, Submission, Task,
                    TaskResult)
from models.plagiarism.plagiarism_report import \
    PlagiarismReport as ActivePlagiarismReport


def test_active_report_is_the_plagiarism_module_one():
    assert PlagiarismReport is ActivePlagiarismReport
    assert PlagiarismReport.__tablename__ == "plagiarism_reports"


@pytest.mark.asyncio
async def test_report_defaults_persist(db, user):
    contest = Contest(
        id=1, user_id=user.id, platform="cf", external_id=1,
        name="C", type="ICPC", unofficial=False,
    )
    db.add(contest)
    await db.flush()

    report = PlagiarismReport(contest_id=1, threshold=0.8, only_ok=False)
    db.add(report)
    await db.commit()
    await db.refresh(report)

    assert report.status == "processing"      # default
    assert report.ban_threshold is None       # default
    assert isinstance(report.created_at, datetime)
    assert report.pairs == []


@pytest.mark.asyncio
async def test_report_cascade_deletes_pairs(db, user):
    contest = Contest(
        id=1, user_id=user.id, platform="cf", external_id=1,
        name="C", type="ICPC", unofficial=False,
    )
    db.add(contest)
    await db.flush()
    part = Participant(id=1, user_id=user.id, login="a", name="A")
    db.add(part)
    await db.flush()
    task = Task(id="t1", contest_id=1, short_name="A", full_name="Apple", max_score=100)
    cp = ContestParticipant(id=1, contest_id=1, participant_id=1, login="a", name="A", score=0.0)
    db.add_all([task, cp])
    await db.flush()
    tr = TaskResult(id=1, contest_participant_id=1, task_id="t1", score=0, tries_count=0, verdict="OK")
    db.add(tr)
    await db.flush()
    for sid in ("s1", "s2"):
        db.add(Submission(
            id=sid, contest_id=1, task_result_id=1, participant_login="a",
            task_name="Apple", send_time=datetime(2026, 1, 1), language="C++",
            score=0, verdict="OK", run_time=timedelta(milliseconds=1),
            memory_bytes=1, source="x",
        ))
    await db.flush()

    report = PlagiarismReport(id=1, contest_id=1, threshold=0.8, only_ok=False)
    db.add(report)
    await db.flush()
    pair = PairOfBannedSubmissions(
        contest_id=1, report_id=1, first_submission_id="s1",
        second_submission_id="s2", percentage=95.0,
    )
    db.add(pair)
    await db.commit()

    await db.refresh(report)
    assert len(report.pairs) == 1

    await db.delete(report)
    await db.commit()

    from sqlalchemy import select
    remaining = await db.execute(select(PairOfBannedSubmissions))
    assert remaining.scalars().all() == []
