"""Unit tests for api/user/plagiarism/base_plagiarism.py.

Covers the pure language-normalisation helper, the picklable subprocess
worker (with plagiarism_cpp mocked by the root conftest), and the
ban/unban TaskResult helpers against the in-memory DB.
"""
from base64 import b64encode
from datetime import datetime, timedelta

import pytest

import api.user.plagiarism.base_plagiarism as plag
from api.user.plagiarism.base_plagiarism import (
    PlagiarismCheckBody, _ban_task_result_for_submission,
    _normalize_language_display, _run_plagiarism_check,
    _unban_task_result_for_submission, run_plagiarism_check)
from models import (Contest, ContestParticipant, Participant, PlagiarismReport,
                    Submission, Task, TaskResult)


# ── _normalize_language_display ──────────────────────────────────────────────
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("GNU G++17 7.3.0", "C++"),
        ("Clang++17 Diagnostics", "C++"),
        ("Python 3.11", "Python"),
        ("Python 2.7", "Python"),
        ("PyPy 3-64", "PyPy"),
        ("PyPy 2", "PyPy"),
        ("Java 17", "Java"),
        ("JavaScript V8 4.8", "JavaScript"),
        ("Node.js 15", "JavaScript"),
        ("Kotlin 1.9", "Kotlin"),
        ("C# 8", "C#"),
        ("GNU C11", "C"),
        ("Rust 1.75", "Rust"),
        ("Go 1.22", "Go"),
        ("Haskell GHC", "Haskell"),
        ("TypeScript 5", "TypeScript"),
        ("Ruby 3", "Ruby"),
        ("PHP 8.1", "PHP"),
        ("Some Exotic Lang", "Some Exotic Lang"),
    ],
)
def test_normalize_language_display(raw, expected):
    assert _normalize_language_display(raw) == expected


def test_pypy_precedes_python():
    # "PyPy" contains "py"; must resolve to PyPy not Python.
    assert _normalize_language_display("PyPy 3.10") == "PyPy"


def test_java_not_javascript():
    assert _normalize_language_display("Java 8") == "Java"
    assert _normalize_language_display("JavaScript") == "JavaScript"


# ── PlagiarismCheckBody validation ───────────────────────────────────────────
def test_check_body_threshold_bounds():
    body = PlagiarismCheckBody(threshold=0.5, banThreshold=0.9)
    assert body.threshold == 0.5
    assert body.onlyOk is False

    with pytest.raises(Exception):
        PlagiarismCheckBody(threshold=1.5, banThreshold=0.5)


# ── _run_plagiarism_check (subprocess worker, plagiarism_cpp mocked) ──────────
def test_run_plagiarism_check_returns_empty_with_mock():
    rows = [
        {
            "id": "s1",
            "source": b64encode(b"int main(){}").decode(),
            "participant": "alice",
            "task_name": "A",
        }
    ]
    # Root conftest mocks compute_similarity_pairs to return [].
    assert _run_plagiarism_check(rows, 0.8) == []


def test_run_plagiarism_check_maps_returned_pairs(monkeypatch):
    class _Pair:
        first_submission_id = "s1"
        second_submission_id = "s2"
        plagiarism_percent = 91.5

    monkeypatch.setattr(
        plag.plagiarism_cpp, "compute_similarity_pairs",
        lambda subs, threshold: [_Pair()],
    )
    rows = [
        {"id": "s1", "source": b64encode(b"x").decode(), "participant": "a", "task_name": "A"},
        {"id": "s2", "source": b64encode(b"x").decode(), "participant": "b", "task_name": "A"},
    ]
    result = _run_plagiarism_check(rows, 0.5)
    assert result == [("s1", "s2", 91.5)]


# ── ban / unban helpers ──────────────────────────────────────────────────────
async def _seed_one_submission(db, user, score=100.0):
    contest = Contest(
        id=1, user_id=user.id, platform="cf", external_id=1,
        name="C", type="ICPC", unofficial=False,
    )
    db.add(contest)
    await db.flush()
    part = Participant(id=1, user_id=user.id, login="alice", name="A")
    db.add(part)
    await db.flush()
    task = Task(id="t1", contest_id=1, short_name="A", full_name="Apple", max_score=100)
    cp = ContestParticipant(
        id=1, contest_id=1, participant_id=1, login="alice", name="A", score=score
    )
    db.add_all([task, cp])
    await db.flush()
    tr = TaskResult(
        id=1, contest_participant_id=1, task_id="t1", score=score,
        tries_count=0, verdict="OK", banned=False,
    )
    db.add(tr)
    await db.flush()
    sub = Submission(
        id="sub1", contest_id=1, task_result_id=1, participant_login="alice",
        task_name="Apple", send_time=datetime(2026, 1, 1), language="GNU C++17",
        score=score, verdict="OK", run_time=timedelta(milliseconds=1),
        memory_bytes=1, banned=False, source="x",
    )
    db.add(sub)
    await db.commit()
    return tr, cp, sub


@pytest.mark.asyncio
async def test_ban_zeros_score_and_marks_banned(db, user):
    tr, cp, sub = await _seed_one_submission(db, user, score=100.0)

    await _ban_task_result_for_submission(db, "sub1")
    await db.commit()

    await db.refresh(tr)
    await db.refresh(cp)
    await db.refresh(sub)
    assert tr.banned is True
    assert tr.score == 0
    assert cp.score == 0.0  # 100 - 100
    assert sub.banned is True


@pytest.mark.asyncio
async def test_ban_is_noop_when_already_banned(db, user):
    tr, cp, sub = await _seed_one_submission(db, user, score=50.0)
    tr.banned = True
    await db.commit()

    await _ban_task_result_for_submission(db, "sub1")
    await db.commit()
    await db.refresh(cp)
    # cp.score unchanged because the ban short-circuits on already-banned TR.
    assert cp.score == 50.0


@pytest.mark.asyncio
async def test_unban_restores_score(db, user):
    tr, cp, sub = await _seed_one_submission(db, user, score=100.0)
    # Ban first, then unban.
    await _ban_task_result_for_submission(db, "sub1")
    await db.commit()

    await _unban_task_result_for_submission(db, "sub1")
    await db.commit()

    await db.refresh(tr)
    await db.refresh(cp)
    await db.refresh(sub)
    assert tr.banned is False
    assert tr.score == 100.0  # restored from max submission score
    assert cp.score == 100.0
    assert sub.banned is False


@pytest.mark.asyncio
async def test_ban_unknown_submission_is_noop(db, user):
    await _seed_one_submission(db, user)
    # Should not raise for a non-existent submission id.
    await _ban_task_result_for_submission(db, "does-not-exist")
    await _unban_task_result_for_submission(db, "does-not-exist")
    await db.commit()


# ── run_plagiarism_check endpoint (background task suppressed) ────────────────
@pytest.mark.asyncio
async def test_run_check_creates_report(db, user, monkeypatch):
    contest = Contest(
        id=1, user_id=user.id, platform="cf", external_id=1,
        name="C", type="ICPC", unofficial=False,
    )
    db.add(contest)
    await db.commit()

    # Suppress the spawned background processing task.
    monkeypatch.setattr(plag.asyncio, "create_task", lambda coro: coro.close())

    body = PlagiarismCheckBody(threshold=0.7, banThreshold=0.9, onlyOk=True)
    result = await run_plagiarism_check(
        contest_id=1, body=body, user_id=user.id, db=db
    )

    assert result["status"] == "processing"
    report_id = result["reportId"]
    report = await db.get(PlagiarismReport, report_id)
    assert report is not None
    assert report.status == "processing"
    assert report.threshold == 0.7
    assert report.ban_threshold == 0.9
    assert report.only_ok is True


@pytest.mark.asyncio
async def test_run_check_unknown_contest_raises_404(db, user, monkeypatch):
    monkeypatch.setattr(plag.asyncio, "create_task", lambda coro: coro.close())
    body = PlagiarismCheckBody(threshold=0.5, banThreshold=0.5)
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await run_plagiarism_check(contest_id=999, body=body, user_id=user.id, db=db)
    assert exc.value.status_code == 404
