"""Unit tests for api/user/contests.py.

Route handlers are invoked DIRECTLY (not over HTTP), passing the seeded
``user``/``db`` fixtures plus explicit path/query params. Covers happy paths,
404 ownership / not-found branches, empty states, search/pagination and the
visual-analytics aggregation branches.
"""
from base64 import b64encode
from datetime import datetime, timedelta

import pytest

from api.user.contests import (
    delete_contest,
    get_contest_overview,
    get_contest_submissions_headers,
    get_contest_table,
    get_submission_source,
    get_user_contests,
    get_visual_analytics,
)
from models import Contest, ContestParticipant, Submission, Task, TaskResult
from models.participant.participant import Participant


# --------------------------------------------------------------------------- #
# Seed helpers
# --------------------------------------------------------------------------- #
async def _make_contest(db, user, **kw):
    defaults = dict(
        user_id=user.id,
        platform="cf",
        external_id=1001,
        name="Test Contest",
        type="ICPC",
        unofficial=False,
        start_time=datetime(2026, 1, 1, 10, 0, 0),
        duration=timedelta(hours=2),
    )
    defaults.update(kw)
    c = Contest(**defaults)
    db.add(c)
    await db.commit()
    await db.refresh(c)
    return c


async def _make_participant(db, user):
    p = Participant(user_id=user.id, login="plog", name="PName", rating=1500)
    db.add(p)
    await db.flush()
    return p


async def _make_contest_participant(db, contest, participant, **kw):
    defaults = dict(
        contest_id=contest.id,
        participant_id=participant.id,
        login="plog",
        name="PName",
        score=0.0,
    )
    defaults.update(kw)
    cp = ContestParticipant(**defaults)
    db.add(cp)
    await db.flush()
    return cp


async def _make_task(db, contest, task_id, short, full, max_score=100.0):
    t = Task(
        id=task_id,
        contest_id=contest.id,
        short_name=short,
        full_name=full,
        max_score=max_score,
    )
    db.add(t)
    await db.flush()
    return t


async def _make_result(db, cp, task, **kw):
    defaults = dict(
        contest_participant_id=cp.id,
        task_id=task.id,
        score=100.0,
        tries_count=1,
        verdict="OK",
        last_success_time=datetime(2026, 1, 1, 10, 30, 0),
        banned=False,
    )
    defaults.update(kw)
    r = TaskResult(**defaults)
    db.add(r)
    await db.flush()
    return r


async def _make_submission(db, contest, task_result_id, **kw):
    defaults = dict(
        id="sub-1",
        contest_id=contest.id,
        task_result_id=task_result_id,
        participant_login="plog",
        task_name="A",
        send_time=datetime(2026, 1, 1, 10, 15, 0),
        language="C++",
        score=100.0,
        verdict="OK",
        run_time=timedelta(seconds=1),
        memory_bytes=1024,
        banned=False,
        source=None,
    )
    defaults.update(kw)
    s = Submission(**defaults)
    db.add(s)
    await db.flush()
    return s


# --------------------------------------------------------------------------- #
# get_user_contests
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_list_empty(db, user):
    result = await get_user_contests(user_id=user.id, db=db)
    assert result == []


@pytest.mark.asyncio
async def test_list_returns_owned_contests_desc(db, user):
    c1 = await _make_contest(db, user, name="First", external_id=1)
    c2 = await _make_contest(db, user, name="Second", external_id=2)
    result = await get_user_contests(user_id=user.id, db=db)
    assert [r["id"] for r in result] == [c2.id, c1.id]  # desc by id
    row = result[0]
    assert row["name"] == "Second"
    assert row["platform"] == "cf"
    assert row["start_time"] is not None
    assert row["duration"] is not None


@pytest.mark.asyncio
async def test_list_handles_null_start_time_and_duration(db, user):
    await _make_contest(db, user, start_time=None, duration=None)
    result = await get_user_contests(user_id=user.id, db=db)
    assert result[0]["start_time"] is None
    assert result[0]["duration"] is None


@pytest.mark.asyncio
async def test_list_only_returns_own_contests(db, user):
    # contest owned by a different user_id should not show up
    await _make_contest(db, user, user_id=user.id + 999, external_id=77)
    result = await get_user_contests(user_id=user.id, db=db)
    assert result == []


# --------------------------------------------------------------------------- #
# get_contest_overview
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_overview_not_found(db, user):
    with pytest.raises(Exception) as exc:
        await get_contest_overview(contest_id=12345, user_id=user.id, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_overview_counts(db, user):
    c = await _make_contest(db, user)
    p = await _make_participant(db, user)
    cp = await _make_contest_participant(db, c, p)
    t = await _make_task(db, c, "tA", "A", "Apples")
    r = await _make_result(db, cp, t)
    await _make_submission(db, c, r.id)
    await db.commit()

    result = await get_contest_overview(contest_id=c.id, user_id=user.id, db=db)
    assert result["id"] == c.id
    assert result["name"] == "Test Contest"
    assert result["type"] == "cf"  # maps to platform
    assert result["stats"] == {"tasks": 1, "participants": 1, "submissions": 1}


# --------------------------------------------------------------------------- #
# get_contest_table
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_table_not_found(db, user):
    with pytest.raises(Exception) as exc:
        await get_contest_table(contest_id=999, user_id=user.id, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_table_empty_participants(db, user):
    c = await _make_contest(db, user)
    await db.commit()
    result = await get_contest_table(
        contest_id=c.id, page=1, per_page=50, search="", user_id=user.id, db=db
    )
    assert result["rows"] == []
    assert result["pagination"]["total"] == 0
    assert result["pagination"]["total_pages"] == 1  # empty -> 1


@pytest.mark.asyncio
async def test_table_ranking_and_banned_exclusion(db, user):
    c = await _make_contest(db, user)
    p = await _make_participant(db, user)
    t_a = await _make_task(db, c, "tA", "A", "Apples")
    t_b = await _make_task(db, c, "tB", "B", "Bananas")

    high = await _make_contest_participant(db, c, p, login="high", name="High")
    low = await _make_contest_participant(db, c, p, login="low", name="Low")

    # high: A=100 (ok), B=50 banned -> effective 100
    await _make_result(db, high, t_a, score=100.0)
    await _make_result(db, high, t_b, score=50.0, banned=True)
    # low: A=30
    await _make_result(db, low, t_a, score=30.0)
    await db.commit()

    result = await get_contest_table(
        contest_id=c.id, page=1, per_page=50, search="", user_id=user.id, db=db
    )
    rows = result["rows"]
    assert rows[0]["login"] == "high"
    assert rows[0]["rank"] == 1
    assert rows[0]["total_score"] == 100.0  # banned B excluded
    assert rows[1]["login"] == "low"
    assert rows[1]["rank"] == 2
    # tasks listed sorted by short_name
    assert [tk["short_name"] for tk in result["tasks"]] == ["A", "B"]
    # row results length == number of tasks; missing result -> defaults
    assert len(rows[1]["results"]) == 2
    b_cell = rows[1]["results"][1]
    assert b_cell["verdict"] == "NULL"
    assert b_cell["score"] == 0


@pytest.mark.asyncio
async def test_table_search_filter(db, user):
    c = await _make_contest(db, user)
    p = await _make_participant(db, user)
    await _make_contest_participant(db, c, p, login="alice", name="Alice")
    await _make_contest_participant(db, c, p, login="bob", name="Bob")
    await db.commit()

    result = await get_contest_table(
        contest_id=c.id, page=1, per_page=50, search="ali", user_id=user.id, db=db
    )
    assert result["pagination"]["total"] == 1
    assert result["rows"][0]["login"] == "alice"


@pytest.mark.asyncio
async def test_table_pagination_offset(db, user):
    c = await _make_contest(db, user)
    p = await _make_participant(db, user)
    t_a = await _make_task(db, c, "tA", "A", "Apples")
    for i in range(3):
        cp = await _make_contest_participant(
            db, c, p, login=f"u{i}", name=f"U{i}"
        )
        await _make_result(db, cp, t_a, score=float(100 - i))
    await db.commit()

    page2 = await get_contest_table(
        contest_id=c.id, page=2, per_page=10, search="", user_id=user.id, db=db
    )
    # only 3 participants, page 2 with per_page 10 -> empty
    assert page2["rows"] == []
    assert page2["pagination"]["page"] == 2


# --------------------------------------------------------------------------- #
# get_contest_submissions_headers
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_submissions_list_empty(db, user):
    c = await _make_contest(db, user)
    await db.commit()
    result = await get_contest_submissions_headers(
        contest_id=c.id, page=1, per_page=50, search="", user_id=user.id, db=db
    )
    assert result["items"] == []
    assert result["pagination"]["total"] == 0
    assert result["pagination"]["total_pages"] == 1


@pytest.mark.asyncio
async def test_submissions_list_returns_items(db, user):
    c = await _make_contest(db, user)
    p = await _make_participant(db, user)
    cp = await _make_contest_participant(db, c, p)
    t = await _make_task(db, c, "tA", "A", "Apples")
    r = await _make_result(db, cp, t)
    await _make_submission(
        db, c, r.id, id="s1", participant_login="alice", task_name="A"
    )
    await _make_submission(
        db,
        c,
        r.id,
        id="s2",
        participant_login="bob",
        task_name="B",
        send_time=datetime(2026, 1, 1, 11, 0, 0),
    )
    await db.commit()

    result = await get_contest_submissions_headers(
        contest_id=c.id, page=1, per_page=50, search="", user_id=user.id, db=db
    )
    assert result["pagination"]["total"] == 2
    # ordered by send_time desc -> s2 first
    assert result["items"][0]["id"] == "s2"


@pytest.mark.asyncio
async def test_submissions_list_search(db, user):
    c = await _make_contest(db, user)
    p = await _make_participant(db, user)
    cp = await _make_contest_participant(db, c, p)
    t = await _make_task(db, c, "tA", "A", "Apples")
    r = await _make_result(db, cp, t)
    await _make_submission(db, c, r.id, id="s1", participant_login="alice")
    await _make_submission(db, c, r.id, id="s2", participant_login="bob")
    await db.commit()

    result = await get_contest_submissions_headers(
        contest_id=c.id, page=1, per_page=50, search="alice", user_id=user.id, db=db
    )
    assert result["pagination"]["total"] == 1
    assert result["items"][0]["participant_login"] == "alice"


# --------------------------------------------------------------------------- #
# get_submission_source
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_submission_source_decodes_b64(db, user):
    c = await _make_contest(db, user)
    p = await _make_participant(db, user)
    cp = await _make_contest_participant(db, c, p)
    t = await _make_task(db, c, "tA", "A", "Apples")
    r = await _make_result(db, cp, t)
    encoded = b64encode(b"int main(){}").decode()
    await _make_submission(db, c, r.id, id="srcsub", source=encoded)
    await db.commit()

    result = await get_submission_source(
        submission_id="srcsub", user_id=user.id, db=db
    )
    assert result["id"] == "srcsub"
    assert result["source"] == "int main(){}"
    assert result["run_time"] == str(timedelta(seconds=1))


# --------------------------------------------------------------------------- #
# get_visual_analytics
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_visual_analytics_not_found(db, user):
    with pytest.raises(Exception) as exc:
        await get_visual_analytics(contest_id=999, user_id=user.id, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_visual_analytics_wrong_owner(db, user):
    # contest exists but belongs to another user -> filter_by user_id misses
    c = await _make_contest(db, user, user_id=user.id + 500)
    await db.commit()
    with pytest.raises(Exception) as exc:
        await get_visual_analytics(contest_id=c.id, user_id=user.id, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_visual_analytics_empty(db, user):
    c = await _make_contest(db, user)
    await db.commit()
    result = await get_visual_analytics(contest_id=c.id, user_id=user.id, db=db)
    assert result["contest_name"] == "Test Contest"
    assert result["tasks"] == []
    assert result["task_stats"] == []
    assert result["score_distribution"] == []
    assert result["language_breakdown"] == []
    assert result["first_solves"] == []


@pytest.mark.asyncio
async def test_visual_analytics_full(db, user):
    start = datetime(2026, 1, 1, 10, 0, 0)
    c = await _make_contest(db, user, start_time=start)
    p = await _make_participant(db, user)
    cp1 = await _make_contest_participant(db, c, p, login="alice", score=100.0)
    cp2 = await _make_contest_participant(db, c, p, login="bob", score=50.0)
    t_a = await _make_task(db, c, "tA", "A", "Apples")
    t_b = await _make_task(db, c, "tB", "B", "Bananas")
    r1 = await _make_result(db, cp1, t_a)
    r2 = await _make_result(db, cp2, t_b)

    # alice solves A (OK) at +20min; uses short name "A"
    await _make_submission(
        db, c, r1.id, id="sa1", participant_login="alice", task_name="A",
        verdict="OK", send_time=start + timedelta(minutes=20), language="C++",
    )
    # bob WA on A using full name "Apples" (full->short mapping path), at +5
    await _make_submission(
        db, c, r2.id, id="sb1", participant_login="bob", task_name="Apples",
        verdict="WA", send_time=start + timedelta(minutes=5), language="Python",
    )
    # a TLE-variant verdict and an RE-variant + unknown task name (ignored)
    await _make_submission(
        db, c, r2.id, id="sb2", participant_login="bob", task_name="A",
        verdict="TLE", send_time=start + timedelta(minutes=10), language="Python",
    )
    await _make_submission(
        db, c, r2.id, id="sb3", participant_login="bob", task_name="B",
        verdict="RUNTIME_ERROR", send_time=start + timedelta(minutes=12),
        language="Java",
    )
    # negative delta (before start) -> skipped in buckets
    await _make_submission(
        db, c, r2.id, id="sb4", participant_login="bob", task_name="A",
        verdict="OK", send_time=start - timedelta(minutes=5), language="C++",
    )
    # unknown task name -> to_short returns None, skipped
    await _make_submission(
        db, c, r2.id, id="sb5", participant_login="bob", task_name="ZZZ",
        verdict="OK", send_time=start + timedelta(minutes=30), language="Go",
    )
    await db.commit()

    result = await get_visual_analytics(contest_id=c.id, user_id=user.id, db=db)

    assert result["tasks"] == ["A", "B"]

    # task_stats for A: subs with task mapping to A = sa1(OK), sb1(WA via full),
    # sb2(TLE), sb4(OK before start still counts for stats), = 4
    stats_a = next(s for s in result["task_stats"] if s["task"] == "A")
    assert stats_a["ok"] == 2  # sa1 + sb4
    assert stats_a["wa"] == 1
    assert stats_a["tle"] == 1
    assert stats_a["full_name"] == "Apples"
    assert stats_a["solvers"] == 2  # alice + bob both have an OK on A

    stats_b = next(s for s in result["task_stats"] if s["task"] == "B")
    assert stats_b["re"] == 1

    # submissions_over_time for A non-empty
    assert result["submissions_over_time"]["A"]

    # score distribution built from participant scores (100, 50)
    assert result["score_distribution"]
    total_count = sum(b["count"] for b in result["score_distribution"])
    assert total_count == 2

    # language breakdown sorted desc by count
    langs = result["language_breakdown"]
    assert langs[0]["count"] >= langs[-1]["count"]

    # first solves: A solved earliest by bob (sb4 before-start delta is negative
    # so minute < alice's 20) -> first solve login is bob for A
    fs_a = next(f for f in result["first_solves"] if f["task"] == "A")
    assert fs_a["login"] == "bob"


@pytest.mark.asyncio
async def test_visual_analytics_task_without_valid_subs(db, user):
    # Task B exists but receives no usable submissions:
    #  - one submission has an empty task_name (skipped in bucket loop)
    #  - no submission maps to B at all -> empty buckets + empty task_subs.
    start = datetime(2026, 1, 1, 10, 0, 0)
    c = await _make_contest(db, user, start_time=start)
    p = await _make_participant(db, user)
    cp = await _make_contest_participant(db, c, p, login="alice", score=10.0)
    t_a = await _make_task(db, c, "tA", "A", "Apples")
    t_b = await _make_task(db, c, "tB", "B", "Bananas")
    r = await _make_result(db, cp, t_a)

    await _make_submission(
        db, c, r.id, id="va1", participant_login="alice", task_name="A",
        verdict="OK", send_time=start + timedelta(minutes=5), language="C++",
    )
    # empty task_name -> exercises the `not sub.task_name` continue branch
    await _make_submission(
        db, c, r.id, id="va2", participant_login="alice", task_name="",
        verdict="OK", send_time=start + timedelta(minutes=6), language="C++",
    )
    await db.commit()

    result = await get_visual_analytics(contest_id=c.id, user_id=user.id, db=db)
    # B has no submissions -> empty bucket list + omitted from task_stats
    assert result["submissions_over_time"]["B"] == []
    assert all(s["task"] != "B" for s in result["task_stats"])


@pytest.mark.asyncio
async def test_visual_analytics_start_time_fallback(db, user):
    # No contest start_time -> derived from earliest submission send_time
    c = await _make_contest(db, user, start_time=None)
    p = await _make_participant(db, user)
    cp = await _make_contest_participant(db, c, p, login="alice", score=None)
    t_a = await _make_task(db, c, "tA", "A", "Apples")
    r = await _make_result(db, cp, t_a)
    base = datetime(2026, 2, 1, 9, 0, 0)
    await _make_submission(
        db, c, r.id, id="z1", participant_login="alice", task_name="A",
        verdict="OK", send_time=base, language="C++",
    )
    await db.commit()

    result = await get_visual_analytics(contest_id=c.id, user_id=user.id, db=db)
    # score_distribution empty because participant score is None
    assert result["score_distribution"] == []
    # first solve present (start derived from sub) at minute 0
    assert result["first_solves"][0]["minute"] == 0


# --------------------------------------------------------------------------- #
# delete_contest
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_delete_not_found(db, user):
    with pytest.raises(Exception) as exc:
        await delete_contest(contest_id=999, user_id=user.id, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_wrong_owner(db, user):
    c = await _make_contest(db, user, user_id=user.id + 500)
    await db.commit()
    with pytest.raises(Exception) as exc:
        await delete_contest(contest_id=c.id, user_id=user.id, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_delete_success(db, user):
    c = await _make_contest(db, user)
    await db.commit()
    result = await delete_contest(contest_id=c.id, user_id=user.id, db=db)
    assert result == {"message": "Contest deleted successfully"}
    # confirm gone
    again = await get_user_contests(user_id=user.id, db=db)
    assert again == []
