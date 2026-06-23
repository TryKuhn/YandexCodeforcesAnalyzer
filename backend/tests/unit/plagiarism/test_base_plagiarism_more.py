"""Complementary unit tests for api/user/plagiarism/base_plagiarism.py.

The existing ``test_base_plagiarism.py`` covers language normalisation, the
subprocess worker and the low-level ban/unban helpers.  This file exercises the
remaining HTTP endpoints (reports listing, submission meta, paginated report
view with search/task filters, pair detail, task-level and pair-level
ban/unban) and the ``process_plagiarism_report`` background routine across its
branches.  ``plagiarism_cpp`` is mocked by the root conftest; network/DB Session
is monkeypatched per-test where needed.
"""
from base64 import b64encode
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

import pytest
from fastapi import HTTPException

import api.user.plagiarism.base_plagiarism as plag
from api.user.plagiarism.base_plagiarism import (
    PlagiarismCheckBody,
    ban_pair_submission,
    ban_report_task,
    get_contest_reports,
    get_contest_submissions_meta,
    get_pair,
    get_report,
    process_plagiarism_report,
    run_plagiarism_check,
    unban_pair_submission,
    unban_report_task,
)
from models import (
    Contest,
    ContestParticipant,
    PairOfBannedSubmissions,
    Participant,
    PlagiarismReport,
    Submission,
    Task,
    TaskResult,
)


# ── seeding helpers ──────────────────────────────────────────────────────────
async def _seed_contest(db, user, contest_id=1):
    contest = Contest(
        id=contest_id, user_id=user.id, platform="cf", external_id=contest_id,
        name="C", type="ICPC", unofficial=False,
    )
    db.add(contest)
    await db.flush()
    return contest


async def _seed_submission(
    db, user, *, sub_id, contest_id=1, tr_id, cp_id, part_id,
    login="alice", name="Alice", task_name="Apple", task_id=None,
    language="GNU C++17", score=100.0, verdict="OK", banned=False,
    source="aGVsbG8=", send_time=None,
):
    """Create the full Participant→ContestParticipant→TaskResult→Submission chain."""
    if task_id is None:
        task_id = f"task-{sub_id}"
    part = Participant(id=part_id, user_id=user.id, login=login, name=name)
    db.add(part)
    await db.flush()
    cp = ContestParticipant(
        id=cp_id, contest_id=contest_id, participant_id=part_id,
        login=login, name=name, score=score,
    )
    task = Task(id=task_id, contest_id=contest_id, short_name=task_name,
                full_name=task_name, max_score=100)
    db.add_all([cp, task])
    await db.flush()
    tr = TaskResult(
        id=tr_id, contest_participant_id=cp_id, task_id=task_id, score=score,
        tries_count=0, verdict=verdict, banned=banned,
    )
    db.add(tr)
    await db.flush()
    sub = Submission(
        id=sub_id, contest_id=contest_id, task_result_id=tr_id,
        participant_login=login, task_name=task_name,
        send_time=send_time or datetime(2026, 1, 1), language=language,
        score=score, verdict=verdict, run_time=timedelta(milliseconds=1),
        memory_bytes=1, banned=banned, source=source,
    )
    db.add(sub)
    await db.flush()
    return cp, tr, sub


async def _seed_report(db, *, report_id=1, contest_id=1, status="completed"):
    report = PlagiarismReport(
        id=report_id, contest_id=contest_id, status=status,
        threshold=0.5, ban_threshold=0.9, only_ok=False,
    )
    db.add(report)
    await db.flush()
    return report


async def _seed_pair(db, *, pair_id, contest_id=1, report_id, first, second, pct):
    pair = PairOfBannedSubmissions(
        id=pair_id, contest_id=contest_id, report_id=report_id,
        first_submission_id=first, second_submission_id=second, percentage=pct,
    )
    db.add(pair)
    await db.flush()
    return pair


# ── get_contest_reports ──────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_get_contest_reports_lists_with_pairs_count(db, user):
    await _seed_contest(db, user)
    await _seed_submission(db, user, sub_id="s1", tr_id=1, cp_id=1, part_id=1)
    await _seed_submission(db, user, sub_id="s2", tr_id=2, cp_id=2, part_id=2,
                           login="bob", name="Bob")
    r1 = await _seed_report(db, report_id=1)
    r2 = await _seed_report(db, report_id=2, status="processing")
    await _seed_pair(db, pair_id=1, report_id=1, first="s1", second="s2", pct=80.0)
    await db.commit()

    result = await get_contest_reports(contest_id=1, user_id=user.id, db=db)
    # Ordered by id desc → report 2 first.
    assert [r["id"] for r in result] == [2, 1]
    by_id = {r["id"]: r for r in result}
    assert by_id[1]["pairs_count"] == 1
    assert by_id[2]["pairs_count"] == 0
    assert by_id[1]["status"] == "completed"


@pytest.mark.asyncio
async def test_get_contest_reports_unknown_contest_404(db, user):
    with pytest.raises(HTTPException) as exc:
        await get_contest_reports(contest_id=999, user_id=user.id, db=db)
    assert exc.value.status_code == 404


# ── get_contest_submissions_meta ─────────────────────────────────────────────
@pytest.mark.asyncio
async def test_submissions_meta_normalises_and_sorts(db, user):
    await _seed_contest(db, user)
    await _seed_submission(db, user, sub_id="s1", tr_id=1, cp_id=1, part_id=1,
                           language="GNU C++17", task_name="Banana", task_id="t1")
    await _seed_submission(db, user, sub_id="s2", tr_id=2, cp_id=2, part_id=2,
                           login="bob", language="Python 3.11",
                           task_name="Apple", task_id="t2")
    await db.commit()

    result = await get_contest_submissions_meta(contest_id=1, user_id=user.id, db=db)
    assert result["languages"] == ["C++", "Python"]  # normalised + sorted
    assert result["tasks"] == ["Apple", "Banana"]    # sorted


@pytest.mark.asyncio
async def test_submissions_meta_unknown_contest_404(db, user):
    with pytest.raises(HTTPException) as exc:
        await get_contest_submissions_meta(contest_id=999, user_id=user.id, db=db)
    assert exc.value.status_code == 404


# ── get_report ───────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_get_report_not_found_404(db, user):
    with pytest.raises(HTTPException) as exc:
        await get_report(report_id=123, user_id=user.id, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_report_contest_owned_by_other_user_404(db, user):
    # Report exists but its contest belongs to a different user id.
    await _seed_contest(db, user)
    await _seed_report(db, report_id=1)
    await db.commit()
    with pytest.raises(HTTPException) as exc:
        await get_report(report_id=1, user_id=user.id + 999, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_report_processing_returns_empty(db, user):
    await _seed_contest(db, user)
    await _seed_report(db, report_id=1, status="processing")
    await db.commit()
    result = await get_report(report_id=1, user_id=user.id, db=db)
    assert result["status"] == "processing"
    assert result["pairs"] == []
    assert result["pagination"]["total"] == 0
    assert result["pagination"]["total_pages"] == 1


@pytest.mark.asyncio
async def test_get_report_completed_full_payload(db, user):
    await _seed_contest(db, user)
    cp1, _, _ = await _seed_submission(
        db, user, sub_id="s1", tr_id=1, cp_id=1, part_id=1,
        login="alice", name="Alice", task_name="Apple", task_id="t1")
    await _seed_submission(
        db, user, sub_id="s2", tr_id=2, cp_id=2, part_id=2,
        login="bob", name="Bob", task_name="Apple", task_id="t2")
    await _seed_report(db, report_id=1)
    await _seed_pair(db, pair_id=1, report_id=1, first="s1", second="s2", pct=87.654)
    await db.commit()

    result = await get_report(report_id=1, page=1, per_page=20, task_name=None,
                              search="", user_id=user.id, db=db)
    assert result["status"] == "completed"
    assert len(result["pairs"]) == 1
    p = result["pairs"][0]
    assert p["user1"] == "alice"
    assert p["user1_name"] == "Alice"
    assert p["user2"] == "bob"
    assert p["task_name"] == "Apple"
    assert p["percent"] == 87.65  # rounded to 2dp
    assert result["pagination"]["total"] == 1
    assert "Apple" in result["tasks"]
    # No submission is banned yet.
    assert result["banned_tasks"] == []


@pytest.mark.asyncio
async def test_get_report_banned_tasks_populated(db, user):
    await _seed_contest(db, user)
    await _seed_submission(db, user, sub_id="s1", tr_id=1, cp_id=1, part_id=1,
                           login="alice", task_name="Apple", task_id="t1",
                           banned=True)
    await _seed_submission(db, user, sub_id="s2", tr_id=2, cp_id=2, part_id=2,
                           login="bob", task_name="Apple", task_id="t2")
    await _seed_report(db, report_id=1)
    await _seed_pair(db, pair_id=1, report_id=1, first="s1", second="s2", pct=90.0)
    await db.commit()

    result = await get_report(report_id=1, page=1, per_page=20, task_name=None,
                              search="", user_id=user.id, db=db)
    assert result["banned_tasks"] == ["Apple"]


@pytest.mark.asyncio
async def test_get_report_task_name_and_search_filters(db, user):
    await _seed_contest(db, user)
    # Apple pair (alice/bob), Berry pair (carol/dave)
    await _seed_submission(db, user, sub_id="s1", tr_id=1, cp_id=1, part_id=1,
                           login="alice", task_name="Apple", task_id="t1")
    await _seed_submission(db, user, sub_id="s2", tr_id=2, cp_id=2, part_id=2,
                           login="bob", task_name="Apple", task_id="t2")
    await _seed_submission(db, user, sub_id="s3", tr_id=3, cp_id=3, part_id=3,
                           login="carol", task_name="Berry", task_id="t3")
    await _seed_submission(db, user, sub_id="s4", tr_id=4, cp_id=4, part_id=4,
                           login="dave", task_name="Berry", task_id="t4")
    await _seed_report(db, report_id=1)
    await _seed_pair(db, pair_id=1, report_id=1, first="s1", second="s2", pct=80.0)
    await _seed_pair(db, pair_id=2, report_id=1, first="s3", second="s4", pct=70.0)
    await db.commit()

    # Filter by task_name="Apple" → only the Apple pair.
    by_task = await get_report(report_id=1, page=1, per_page=20,
                               task_name="Apple", search="",
                               user_id=user.id, db=db)
    assert by_task["pagination"]["total"] == 1
    assert by_task["pairs"][0]["task_name"] == "Apple"

    # Search by participant login "carol" → only the Berry pair.
    by_search = await get_report(report_id=1, page=1, per_page=20,
                                 task_name=None, search="CAROL",
                                 user_id=user.id, db=db)
    assert by_search["pagination"]["total"] == 1
    assert by_search["pairs"][0]["user1"] == "carol"


@pytest.mark.asyncio
async def test_get_report_pagination(db, user):
    await _seed_contest(db, user)
    await _seed_report(db, report_id=1)
    # 25 pairs, all on task Apple. Each pair needs two submissions; reuse few subs.
    await _seed_submission(db, user, sub_id="s1", tr_id=1, cp_id=1, part_id=1,
                           login="alice", task_name="Apple", task_id="t1")
    await _seed_submission(db, user, sub_id="s2", tr_id=2, cp_id=2, part_id=2,
                           login="bob", task_name="Apple", task_id="t2")
    for i in range(25):
        await _seed_pair(db, pair_id=100 + i, report_id=1, first="s1",
                         second="s2", pct=float(i))
    await db.commit()

    page1 = await get_report(report_id=1, page=1, per_page=10, task_name=None,
                             search="", user_id=user.id, db=db)
    assert page1["pagination"]["total"] == 25
    assert page1["pagination"]["total_pages"] == 3
    assert len(page1["pairs"]) == 10
    # Ordered by percentage desc → highest first.
    assert page1["pairs"][0]["percent"] == 24.0

    page3 = await get_report(report_id=1, page=3, per_page=10, task_name=None,
                             search="", user_id=user.id, db=db)
    assert len(page3["pairs"]) == 5


# ── get_pair ─────────────────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_get_pair_not_found_404(db, user):
    with pytest.raises(HTTPException) as exc:
        await get_pair(pair_id=42, user_id=user.id, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_pair_wrong_user_404(db, user):
    await _seed_contest(db, user)
    await _seed_submission(db, user, sub_id="s1", tr_id=1, cp_id=1, part_id=1,
                           login="alice", task_id="t1")
    await _seed_submission(db, user, sub_id="s2", tr_id=2, cp_id=2, part_id=2,
                           login="bob", task_id="t2")
    await _seed_report(db, report_id=1)
    await _seed_pair(db, pair_id=1, report_id=1, first="s1", second="s2", pct=88.0)
    await db.commit()
    with pytest.raises(HTTPException) as exc:
        await get_pair(pair_id=1, user_id=user.id + 999, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_pair_decodes_source_and_scores(db, user):
    await _seed_contest(db, user)
    code1 = b64encode(b"int main(){}").decode()
    cp1, tr1, _ = await _seed_submission(
        db, user, sub_id="s1", tr_id=1, cp_id=1, part_id=1, login="alice",
        name="Alice", task_id="t1", source=code1, score=100.0)
    # second submission has invalid base64 source → falls back to raw string.
    await _seed_submission(
        db, user, sub_id="s2", tr_id=2, cp_id=2, part_id=2, login="bob",
        name="Bob", task_id="t2", source="not-base64!!", score=50.0)
    await _seed_report(db, report_id=1)
    await _seed_pair(db, pair_id=1, report_id=1, first="s1", second="s2", pct=77.777)
    await db.commit()

    result = await get_pair(pair_id=1, user_id=user.id, db=db)
    assert result["percent"] == 77.78
    assert result["code1"] == "int main(){}"
    assert result["user1_name"] == "Alice"
    assert result["sub1_banned"] is False
    # _original_score: TaskResult not banned → returns tr.score.
    assert result["score1"] == 100.0
    assert result["score2"] == 50.0


@pytest.mark.asyncio
async def test_get_pair_empty_source_returns_empty_string(db, user):
    await _seed_contest(db, user)
    await _seed_submission(db, user, sub_id="s1", tr_id=1, cp_id=1, part_id=1,
                           login="alice", task_id="t1", source=None)
    await _seed_submission(db, user, sub_id="s2", tr_id=2, cp_id=2, part_id=2,
                           login="bob", task_id="t2", source=None)
    await _seed_report(db, report_id=1)
    await _seed_pair(db, pair_id=1, report_id=1, first="s1", second="s2", pct=60.0)
    await db.commit()
    result = await get_pair(pair_id=1, user_id=user.id, db=db)
    assert result["code1"] == ""
    assert result["code2"] == ""


# ── ban_report_task / unban_report_task ──────────────────────────────────────
@pytest.mark.asyncio
async def test_ban_report_task_bans_all_pairs(db, user):
    await _seed_contest(db, user)
    cp1, tr1, _ = await _seed_submission(
        db, user, sub_id="s1", tr_id=1, cp_id=1, part_id=1, login="alice",
        task_name="Apple", task_id="t1", score=100.0)
    cp2, tr2, _ = await _seed_submission(
        db, user, sub_id="s2", tr_id=2, cp_id=2, part_id=2, login="bob",
        task_name="Apple", task_id="t2", score=80.0)
    await _seed_report(db, report_id=1)
    await _seed_pair(db, pair_id=1, report_id=1, first="s1", second="s2", pct=95.0)
    await db.commit()

    result = await ban_report_task(report_id=1, task_name=None, user_id=user.id, db=db)
    assert result["banned_submissions"] == 2
    await db.refresh(tr1)
    await db.refresh(tr2)
    assert tr1.banned is True and tr2.banned is True


@pytest.mark.asyncio
async def test_ban_report_task_report_404(db, user):
    with pytest.raises(HTTPException) as exc:
        await ban_report_task(report_id=999, task_name=None, user_id=user.id, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_ban_report_task_contest_404(db, user):
    await _seed_contest(db, user)
    await _seed_report(db, report_id=1)
    await db.commit()
    with pytest.raises(HTTPException) as exc:
        await ban_report_task(report_id=1, task_name=None,
                              user_id=user.id + 999, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_ban_report_task_filters_by_task_name(db, user):
    await _seed_contest(db, user)
    cp1, tr1, _ = await _seed_submission(
        db, user, sub_id="s1", tr_id=1, cp_id=1, part_id=1, login="alice",
        task_name="Apple", task_id="t1")
    cp2, tr2, _ = await _seed_submission(
        db, user, sub_id="s2", tr_id=2, cp_id=2, part_id=2, login="bob",
        task_name="Apple", task_id="t2")
    cp3, tr3, _ = await _seed_submission(
        db, user, sub_id="s3", tr_id=3, cp_id=3, part_id=3, login="carol",
        task_name="Berry", task_id="t3")
    cp4, tr4, _ = await _seed_submission(
        db, user, sub_id="s4", tr_id=4, cp_id=4, part_id=4, login="dave",
        task_name="Berry", task_id="t4")
    await _seed_report(db, report_id=1)
    await _seed_pair(db, pair_id=1, report_id=1, first="s1", second="s2", pct=90.0)
    await _seed_pair(db, pair_id=2, report_id=1, first="s3", second="s4", pct=85.0)
    await db.commit()

    result = await ban_report_task(report_id=1, task_name="Apple",
                                   user_id=user.id, db=db)
    assert result["banned_submissions"] == 2
    await db.refresh(tr1)
    await db.refresh(tr3)
    assert tr1.banned is True
    assert tr3.banned is False  # Berry untouched


@pytest.mark.asyncio
async def test_unban_report_task_restores(db, user):
    await _seed_contest(db, user)
    cp1, tr1, _ = await _seed_submission(
        db, user, sub_id="s1", tr_id=1, cp_id=1, part_id=1, login="alice",
        task_name="Apple", task_id="t1", score=100.0)
    cp2, tr2, _ = await _seed_submission(
        db, user, sub_id="s2", tr_id=2, cp_id=2, part_id=2, login="bob",
        task_name="Apple", task_id="t2", score=80.0)
    await _seed_report(db, report_id=1)
    await _seed_pair(db, pair_id=1, report_id=1, first="s1", second="s2", pct=95.0)
    await db.commit()

    await ban_report_task(report_id=1, task_name=None, user_id=user.id, db=db)
    result = await unban_report_task(report_id=1, task_name=None, user_id=user.id, db=db)
    assert result["unbanned_submissions"] == 2
    await db.refresh(tr1)
    await db.refresh(tr2)
    assert tr1.banned is False and tr2.banned is False


@pytest.mark.asyncio
async def test_unban_report_task_report_404(db, user):
    with pytest.raises(HTTPException) as exc:
        await unban_report_task(report_id=999, task_name=None, user_id=user.id, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_unban_report_task_contest_404(db, user):
    await _seed_contest(db, user)
    await _seed_report(db, report_id=1)
    await db.commit()
    with pytest.raises(HTTPException) as exc:
        await unban_report_task(report_id=1, task_name=None,
                                user_id=user.id + 999, db=db)
    assert exc.value.status_code == 404


# ── ban_pair_submission / unban_pair_submission ──────────────────────────────
@pytest.mark.asyncio
async def test_ban_pair_bad_position_400(db, user):
    with pytest.raises(HTTPException) as exc:
        await ban_pair_submission(pair_id=1, position=3, user_id=user.id, db=db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_unban_pair_bad_position_400(db, user):
    with pytest.raises(HTTPException) as exc:
        await unban_pair_submission(pair_id=1, position=0, user_id=user.id, db=db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_ban_pair_not_found_404(db, user):
    with pytest.raises(HTTPException) as exc:
        await ban_pair_submission(pair_id=1, position=1, user_id=user.id, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_ban_pair_wrong_user_404(db, user):
    await _seed_contest(db, user)
    await _seed_submission(db, user, sub_id="s1", tr_id=1, cp_id=1, part_id=1,
                           login="alice", task_id="t1")
    await _seed_submission(db, user, sub_id="s2", tr_id=2, cp_id=2, part_id=2,
                           login="bob", task_id="t2")
    await _seed_report(db, report_id=1)
    await _seed_pair(db, pair_id=1, report_id=1, first="s1", second="s2", pct=90.0)
    await db.commit()
    with pytest.raises(HTTPException) as exc:
        await ban_pair_submission(pair_id=1, position=1,
                                  user_id=user.id + 999, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_ban_then_unban_pair_position_1_and_2(db, user):
    await _seed_contest(db, user)
    cp1, tr1, _ = await _seed_submission(
        db, user, sub_id="s1", tr_id=1, cp_id=1, part_id=1, login="alice",
        task_id="t1", score=100.0)
    cp2, tr2, _ = await _seed_submission(
        db, user, sub_id="s2", tr_id=2, cp_id=2, part_id=2, login="bob",
        task_id="t2", score=80.0)
    await _seed_report(db, report_id=1)
    await _seed_pair(db, pair_id=1, report_id=1, first="s1", second="s2", pct=92.0)
    await db.commit()

    r1 = await ban_pair_submission(pair_id=1, position=1, user_id=user.id, db=db)
    assert r1["banned_submission_id"] == "s1"
    await db.refresh(tr1)
    assert tr1.banned is True

    r2 = await ban_pair_submission(pair_id=1, position=2, user_id=user.id, db=db)
    assert r2["banned_submission_id"] == "s2"
    await db.refresh(tr2)
    assert tr2.banned is True

    u1 = await unban_pair_submission(pair_id=1, position=1, user_id=user.id, db=db)
    assert u1["unbanned_submission_id"] == "s1"
    await db.refresh(tr1)
    assert tr1.banned is False


@pytest.mark.asyncio
async def test_unban_pair_not_found_404(db, user):
    with pytest.raises(HTTPException) as exc:
        await unban_pair_submission(pair_id=1, position=1, user_id=user.id, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_unban_pair_wrong_user_404(db, user):
    await _seed_contest(db, user)
    await _seed_submission(db, user, sub_id="s1", tr_id=1, cp_id=1, part_id=1,
                           login="alice", task_id="t1")
    await _seed_submission(db, user, sub_id="s2", tr_id=2, cp_id=2, part_id=2,
                           login="bob", task_id="t2")
    await _seed_report(db, report_id=1)
    await _seed_pair(db, pair_id=1, report_id=1, first="s1", second="s2", pct=90.0)
    await db.commit()
    with pytest.raises(HTTPException) as exc:
        await unban_pair_submission(pair_id=1, position=2,
                                    user_id=user.id + 999, db=db)
    assert exc.value.status_code == 404


# ── process_plagiarism_report ────────────────────────────────────────────────
def _patch_session(monkeypatch, db):
    """Make ``async with Session() as s`` yield the test db without closing it."""
    @asynccontextmanager
    async def _fake_session():
        yield db

    def _factory():
        return _fake_session()

    monkeypatch.setattr(plag, "Session", _factory)


def _patch_loop_inprocess(monkeypatch):
    """Run the plagiarism worker in-process instead of the ProcessPoolExecutor.

    The real ``ProcessPoolExecutor`` can't pickle the worker under pytest, so we
    swap ``get_running_loop().run_in_executor`` for a direct in-process call
    (which returns ``[]`` via the conftest-mocked ``plagiarism_cpp``).
    """
    async def _call(fn, *args):
        return fn(*args)

    class _FakeLoop:
        def run_in_executor(self, executor, fn, *args):
            return _call(fn, *args)

    monkeypatch.setattr(plag.asyncio, "get_running_loop", lambda: _FakeLoop())


@pytest.mark.asyncio
async def test_process_report_no_pairs_marks_completed(db, user, monkeypatch):
    await _seed_contest(db, user)
    # Two submissions on the same task so a task group of size >= 2 is dispatched.
    await _seed_submission(db, user, sub_id="s1", tr_id=1, cp_id=1, part_id=1,
                           login="alice", task_name="Apple", task_id="t1",
                           source=b64encode(b"a").decode())
    await _seed_submission(db, user, sub_id="s2", tr_id=2, cp_id=2, part_id=2,
                           login="bob", task_name="Apple", task_id="t2",
                           source=b64encode(b"b").decode())
    await _seed_report(db, report_id=1, status="processing")
    await db.commit()

    _patch_session(monkeypatch, db)
    _patch_loop_inprocess(monkeypatch)
    # Root conftest's compute_similarity_pairs returns [] → no pairs.
    await process_plagiarism_report(
        report_id=1, contest_id=1, threshold=0.5, ban_threshold=0.9,
        only_ok=False,
    )

    report = await db.get(PlagiarismReport, 1)
    assert report.status == "completed"
    pairs_q = await db.execute(plag.select(PairOfBannedSubmissions))
    assert pairs_q.scalars().all() == []


@pytest.mark.asyncio
async def test_process_report_persists_pairs_and_autobans(db, user, monkeypatch):
    await _seed_contest(db, user)
    cp1, tr1, _ = await _seed_submission(
        db, user, sub_id="s1", tr_id=1, cp_id=1, part_id=1, login="alice",
        task_name="Apple", task_id="t1", score=100.0,
        source=b64encode(b"same code").decode())
    cp2, tr2, _ = await _seed_submission(
        db, user, sub_id="s2", tr_id=2, cp_id=2, part_id=2, login="bob",
        task_name="Apple", task_id="t2", score=80.0,
        source=b64encode(b"same code").decode())
    await _seed_report(db, report_id=1, status="processing")
    await db.commit()

    _patch_session(monkeypatch, db)

    # Stub the subprocess dispatch: return a 99% pair (above ban_threshold*100=90).
    async def _fake_run_in_executor(executor, fn, group_subs, threshold):
        return [("s1", "s2", 99.0)]

    class _FakeLoop:
        def run_in_executor(self, *args):
            return _fake_run_in_executor(*args)

    monkeypatch.setattr(plag.asyncio, "get_running_loop", lambda: _FakeLoop())

    await process_plagiarism_report(
        report_id=1, contest_id=1, threshold=0.5, ban_threshold=0.9,
        only_ok=False,
    )

    report = await db.get(PlagiarismReport, 1)
    assert report.status == "completed"
    pairs_q = await db.execute(plag.select(PairOfBannedSubmissions))
    pairs = pairs_q.scalars().all()
    assert len(pairs) == 1
    assert pairs[0].percentage == 99.0
    # Auto-ban above threshold.
    await db.refresh(tr1)
    await db.refresh(tr2)
    assert tr1.banned is True and tr2.banned is True


@pytest.mark.asyncio
async def test_process_report_below_ban_threshold_not_banned(db, user, monkeypatch):
    await _seed_contest(db, user)
    cp1, tr1, _ = await _seed_submission(
        db, user, sub_id="s1", tr_id=1, cp_id=1, part_id=1, login="alice",
        task_name="Apple", task_id="t1",
        source=b64encode(b"x").decode())
    cp2, tr2, _ = await _seed_submission(
        db, user, sub_id="s2", tr_id=2, cp_id=2, part_id=2, login="bob",
        task_name="Apple", task_id="t2",
        source=b64encode(b"y").decode())
    await _seed_report(db, report_id=1, status="processing")
    await db.commit()

    _patch_session(monkeypatch, db)

    async def _fake(executor, fn, group_subs, threshold):
        return [("s1", "s2", 50.0)]  # below 0.9*100

    class _FakeLoop:
        def run_in_executor(self, *args):
            return _fake(*args)

    monkeypatch.setattr(plag.asyncio, "get_running_loop", lambda: _FakeLoop())

    await process_plagiarism_report(
        report_id=1, contest_id=1, threshold=0.5, ban_threshold=0.9,
        only_ok=False,
    )

    await db.refresh(tr1)
    assert tr1.banned is False


@pytest.mark.asyncio
async def test_process_report_language_filter_no_match(db, user, monkeypatch):
    # languages=["Rust"] but submissions are C++ → query filters to empty.
    await _seed_contest(db, user)
    await _seed_submission(db, user, sub_id="s1", tr_id=1, cp_id=1, part_id=1,
                           login="alice", task_name="Apple", task_id="t1",
                           language="GNU C++17", source=b64encode(b"a").decode())
    await _seed_report(db, report_id=1, status="processing")
    await db.commit()

    _patch_session(monkeypatch, db)
    await process_plagiarism_report(
        report_id=1, contest_id=1, threshold=0.5, ban_threshold=None,
        only_ok=False, languages=["Rust"],
    )
    report = await db.get(PlagiarismReport, 1)
    assert report.status == "completed"


@pytest.mark.asyncio
async def test_process_report_language_filter_match(db, user, monkeypatch):
    await _seed_contest(db, user)
    await _seed_submission(db, user, sub_id="s1", tr_id=1, cp_id=1, part_id=1,
                           login="alice", task_name="Apple", task_id="t1",
                           language="GNU C++17", source=b64encode(b"a").decode())
    await _seed_submission(db, user, sub_id="s2", tr_id=2, cp_id=2, part_id=2,
                           login="bob", task_name="Apple", task_id="t2",
                           language="GNU G++20", source=b64encode(b"b").decode())
    await _seed_report(db, report_id=1, status="processing")
    await db.commit()

    _patch_session(monkeypatch, db)
    _patch_loop_inprocess(monkeypatch)
    await process_plagiarism_report(
        report_id=1, contest_id=1, threshold=0.5, ban_threshold=None,
        only_ok=False, languages=["C++"], tasks=["Apple"],
    )
    report = await db.get(PlagiarismReport, 1)
    assert report.status == "completed"


@pytest.mark.asyncio
async def test_process_report_failure_marks_failed(db, user, monkeypatch):
    await _seed_contest(db, user)
    await _seed_submission(db, user, sub_id="s1", tr_id=1, cp_id=1, part_id=1,
                           login="alice", task_name="Apple", task_id="t1",
                           source=b64encode(b"a").decode())
    await _seed_submission(db, user, sub_id="s2", tr_id=2, cp_id=2, part_id=2,
                           login="bob", task_name="Apple", task_id="t2",
                           source=b64encode(b"b").decode())
    await _seed_report(db, report_id=1, status="processing")
    await db.commit()

    _patch_session(monkeypatch, db)

    class _FakeLoop:
        def run_in_executor(self, *args):
            raise RuntimeError("boom")

    monkeypatch.setattr(plag.asyncio, "get_running_loop", lambda: _FakeLoop())

    with pytest.raises(RuntimeError):
        await process_plagiarism_report(
            report_id=1, contest_id=1, threshold=0.5, ban_threshold=0.9,
            only_ok=False,
        )

    report = await db.get(PlagiarismReport, 1)
    assert report.status == "failed"


@pytest.mark.asyncio
async def test_process_report_only_ok_filter(db, user, monkeypatch):
    # only_ok=True should exclude the non-OK submission, leaving a single-sub
    # task group (size < 2) so no executor future is dispatched.
    await _seed_contest(db, user)
    await _seed_submission(db, user, sub_id="s1", tr_id=1, cp_id=1, part_id=1,
                           login="alice", task_name="Apple", task_id="t1",
                           verdict="OK", source=b64encode(b"a").decode())
    await _seed_submission(db, user, sub_id="s2", tr_id=2, cp_id=2, part_id=2,
                           login="bob", task_name="Apple", task_id="t2",
                           verdict="WA", source=b64encode(b"b").decode())
    await _seed_report(db, report_id=1, status="processing")
    await db.commit()

    _patch_session(monkeypatch, db)
    await process_plagiarism_report(
        report_id=1, contest_id=1, threshold=0.5, ban_threshold=0.9,
        only_ok=True,
    )
    report = await db.get(PlagiarismReport, 1)
    assert report.status == "completed"
    pairs_q = await db.execute(plag.select(PairOfBannedSubmissions))
    assert pairs_q.scalars().all() == []
