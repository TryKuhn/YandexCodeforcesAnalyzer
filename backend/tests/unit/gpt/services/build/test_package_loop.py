"""Unit tests for the build/auto-repair loop (services.build.package_loop)."""
import pytest

from api.user.gpt.services.build import package_loop as pl


@pytest.fixture(autouse=True)
def _fast_sleep(monkeypatch):
    """Replace asyncio.sleep in the module with an async no-op (no real delay)."""
    async def _no_sleep(_):
        return None

    monkeypatch.setattr(pl.asyncio, "sleep", _no_sleep)
    # Keep timeout small so TIMEOUT paths terminate quickly regardless.
    monkeypatch.setattr(pl, "POLL_INTERVAL", 1)
    monkeypatch.setattr(pl, "POLL_TIMEOUT", 3)


def _stateful_get_packages(states):
    """Build a fake get_packages yielding one state per call (last sticks)."""
    seq = list(states)

    async def fake(problem_id, user_id, db):
        if not seq:
            return []
        cur = seq.pop(0) if len(seq) > 1 else seq[0]
        if cur is None:
            return []
        return [{"state": cur, "comment": f"{cur}-comment", "id": 42}]

    return fake


# --------------------------------------------------------------------------- #
# _poll
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_poll_ready(monkeypatch):
    monkeypatch.setattr(pl, "get_packages",
                        _stateful_get_packages(["PENDING", "READY"]))
    state, comment, pid = await pl._poll(1, 2, None, pl._noop)
    assert state == "READY" and pid == 42


@pytest.mark.asyncio
async def test_poll_failed(monkeypatch):
    monkeypatch.setattr(pl, "get_packages",
                        _stateful_get_packages(["PENDING", "FAILED"]))
    state, comment, pid = await pl._poll(1, 2, None, pl._noop)
    assert state == "FAILED" and comment == "FAILED-comment" and pid == 42


@pytest.mark.asyncio
async def test_poll_timeout_on_persistent_pending(monkeypatch):
    monkeypatch.setattr(pl, "get_packages",
                        _stateful_get_packages(["PENDING"]))
    state, comment, pid = await pl._poll(1, 2, None, pl._noop)
    assert state == "TIMEOUT" and pid is None


@pytest.mark.asyncio
async def test_poll_skips_empty_package_list(monkeypatch):
    # None → empty list (continue), then READY.
    monkeypatch.setattr(pl, "get_packages",
                        _stateful_get_packages([None, "READY"]))
    state, _, pid = await pl._poll(1, 2, None, pl._noop)
    assert state == "READY" and pid == 42


# --------------------------------------------------------------------------- #
# _build_once
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_build_once_commits_builds_and_polls(monkeypatch):
    calls = {"commit": 0, "build": 0}

    async def fake_commit(*a, **k):
        calls["commit"] += 1

    async def fake_build_package(**k):
        calls["build"] += 1

    monkeypatch.setattr(pl, "commit_changes", fake_commit)
    monkeypatch.setattr(pl, "build_package", fake_build_package)
    monkeypatch.setattr(pl, "get_packages",
                        _stateful_get_packages(["READY"]))

    state, _, pid = await pl._build_once(1, 2, None, pl._noop)
    assert state == "READY" and pid == 42
    assert calls["commit"] == 1 and calls["build"] == 1


# --------------------------------------------------------------------------- #
# _finalize
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_finalize_no_groups_returns_empty(task_session, db):
    out = await pl._finalize(task_session, 555, db, None, pl._noop)
    assert out == {}


@pytest.mark.asyncio
async def test_finalize_assigns_and_commits(task_session, db, monkeypatch):
    calls = {"assign": 0, "commit": 0}

    async def fake_assign(sid, pid, uid, groups, db_):
        calls["assign"] += 1
        return {"1": [1, 2]}

    async def fake_commit(*a, **k):
        calls["commit"] += 1

    monkeypatch.setattr(pl, "assign_tests_to_groups", fake_assign)
    monkeypatch.setattr(pl, "commit_changes", fake_commit)

    mapping = await pl._finalize(
        task_session, 555, db, [{"group": "1"}], pl._noop
    )
    assert mapping == {"1": [1, 2]}
    assert calls["assign"] == 1 and calls["commit"] == 1


@pytest.mark.asyncio
async def test_finalize_swallows_commit_error(task_session, db, monkeypatch):
    async def fake_assign(*a, **k):
        return {"1": [1]}

    async def fake_commit(*a, **k):
        raise RuntimeError("commit boom")

    monkeypatch.setattr(pl, "assign_tests_to_groups", fake_assign)
    monkeypatch.setattr(pl, "commit_changes", fake_commit)

    mapping = await pl._finalize(
        task_session, 555, db, [{"group": "1"}], pl._noop
    )
    # commit failure is logged, not raised; mapping still returned.
    assert mapping == {"1": [1]}


# --------------------------------------------------------------------------- #
# build_and_poll
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_build_and_poll_no_problem_id_manual_fix(task_session, db):
    task_session.polygon_problem_id = None
    out = await pl.build_and_poll(db, task_session)
    assert out["status"] == "manual_fix" and out["offender"] is None


@pytest.mark.asyncio
async def test_build_and_poll_ready_returns_done_with_group_map(
    task_session, db, monkeypatch
):
    async def fake_build_once(problem_id, user_id, db_, set_step):
        return "READY", "", 99

    async def fake_finalize(session, pid, db_, groups, set_step):
        return {"1": [1, 2, 3]}

    monkeypatch.setattr(pl, "_build_once", fake_build_once)
    monkeypatch.setattr(pl, "_finalize", fake_finalize)

    out = await pl.build_and_poll(
        db, task_session, scoring_groups=[{"group": "1"}]
    )
    assert out == {"status": "done", "package_id": 99,
                   "group_map": {"1": [1, 2, 3]}}


@pytest.mark.asyncio
async def test_build_and_poll_timeout(task_session, db, monkeypatch):
    async def fake_build_once(*a, **k):
        return "TIMEOUT", "timed out", None

    monkeypatch.setattr(pl, "_build_once", fake_build_once)
    out = await pl.build_and_poll(db, task_session)
    assert out == {"status": "timeout", "error": "timed out"}


@pytest.mark.asyncio
async def test_build_and_poll_failed_unknown_offender_manual_fix(
    task_session, db, monkeypatch
):
    async def fake_build_once(*a, **k):
        return "FAILED", "opaque error", 7

    async def fake_resolve(comment, applicable):
        return None

    monkeypatch.setattr(pl, "_build_once", fake_build_once)
    monkeypatch.setattr(pl, "resolve_offending_file", fake_resolve)

    out = await pl.build_and_poll(db, task_session)
    assert out == {"status": "manual_fix", "offender": None,
                   "error": "opaque error"}


@pytest.mark.asyncio
async def test_build_and_poll_failed_then_fix_succeeds(
    task_session, db, monkeypatch
):
    states = iter([
        ("FAILED", "checker error", 1),   # initial build
        ("READY", "", 50),                 # after the fix
    ])

    async def fake_build_once(*a, **k):
        return next(states)

    async def fake_resolve(comment, applicable):
        return "checker"

    async def fake_get_contents(db_, sid):
        return {"checker": "old code"}

    fix_calls = {"n": 0}

    async def fake_fix(offender, code, error, statement, model,
                       previous_errors=None, related_files=None):
        fix_calls["n"] += 1
        return "new code"

    sync_calls = {"n": 0}

    async def fake_sync_file(db_, session, ft, content):
        sync_calls["n"] += 1

    async def fake_finalize(*a, **k):
        return {}

    monkeypatch.setattr(pl, "_build_once", fake_build_once)
    monkeypatch.setattr(pl, "resolve_offending_file", fake_resolve)
    monkeypatch.setattr(pl, "get_all_file_contents", fake_get_contents)
    monkeypatch.setattr(pl.fix_gen, "fix", fake_fix)
    monkeypatch.setattr(pl, "sync_file", fake_sync_file)
    monkeypatch.setattr(pl, "_finalize", fake_finalize)

    out = await pl.build_and_poll(db, task_session)
    assert out == {"status": "done", "package_id": 50}
    assert fix_calls["n"] == 1 and sync_calls["n"] == 1


@pytest.mark.asyncio
async def test_build_and_poll_fix_exception_manual_fix(
    task_session, db, monkeypatch
):
    async def fake_build_once(*a, **k):
        return "FAILED", "checker error", 1

    async def fake_resolve(comment, applicable):
        return "checker"

    async def fake_get_contents(db_, sid):
        return {"checker": "old"}

    async def fake_fix(*a, **k):
        raise RuntimeError("llm down")

    monkeypatch.setattr(pl, "_build_once", fake_build_once)
    monkeypatch.setattr(pl, "resolve_offending_file", fake_resolve)
    monkeypatch.setattr(pl, "get_all_file_contents", fake_get_contents)
    monkeypatch.setattr(pl.fix_gen, "fix", fake_fix)

    out = await pl.build_and_poll(db, task_session)
    assert out == {"status": "manual_fix", "offender": "checker",
                   "error": "checker error"}


@pytest.mark.asyncio
async def test_build_and_poll_attempts_exhausted_manual_fix(
    task_session, db, monkeypatch
):
    # Always FAILED → after MAX_FILE_FIX_ATTEMPTS rebuilds, escalate.
    async def fake_build_once(*a, **k):
        return "FAILED", "still broken", 1

    async def fake_resolve(comment, applicable):
        return "checker"

    async def fake_get_contents(db_, sid):
        return {"checker": "old"}

    async def fake_fix(*a, **k):
        return "attempted code"

    async def fake_sync_file(*a, **k):
        return None

    monkeypatch.setattr(pl, "_build_once", fake_build_once)
    monkeypatch.setattr(pl, "resolve_offending_file", fake_resolve)
    monkeypatch.setattr(pl, "get_all_file_contents", fake_get_contents)
    monkeypatch.setattr(pl.fix_gen, "fix", fake_fix)
    monkeypatch.setattr(pl, "sync_file", fake_sync_file)

    out = await pl.build_and_poll(db, task_session)
    assert out["status"] == "manual_fix"
    assert out["offender"] == "checker"
    assert out["error"] == "still broken"


@pytest.mark.asyncio
async def test_build_and_poll_passes_companions_for_generator(
    task_session, db, monkeypatch
):
    """When the offender is 'generator', the script companion is passed read-only."""
    states = iter([
        ("FAILED", "generator error", 1),
        ("READY", "", 50),
    ])

    async def fake_build_once(*a, **k):
        return next(states)

    async def fake_resolve(comment, applicable):
        return "generator"

    async def fake_get_contents(db_, sid):
        return {"generator": "gen code", "script": "script code"}

    captured = {}

    async def fake_fix(offender, code, error, statement, model,
                       previous_errors=None, related_files=None):
        captured["related"] = related_files
        return "fixed gen"

    async def fake_sync_file(*a, **k):
        return None

    async def fake_finalize(*a, **k):
        return {}

    monkeypatch.setattr(pl, "_build_once", fake_build_once)
    monkeypatch.setattr(pl, "resolve_offending_file", fake_resolve)
    monkeypatch.setattr(pl, "get_all_file_contents", fake_get_contents)
    monkeypatch.setattr(pl.fix_gen, "fix", fake_fix)
    monkeypatch.setattr(pl, "sync_file", fake_sync_file)
    monkeypatch.setattr(pl, "_finalize", fake_finalize)

    out = await pl.build_and_poll(db, task_session)
    assert out["status"] == "done"
    assert captured["related"] == {"script": "script code"}
