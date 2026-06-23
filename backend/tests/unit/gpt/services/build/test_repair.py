"""Unit tests for the build-with-repair entrypoint (services.build.repair)."""
import pytest

from api.user.gpt.services.build import repair
from models.task.session import PipelineStage


class _FakeSessionCtx:
    """Async context manager that yields a pre-existing test db session."""

    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, *exc):
        return False


def _patch_session(monkeypatch, db):
    monkeypatch.setattr(repair, "Session", lambda: _FakeSessionCtx(db))


@pytest.mark.asyncio
async def test_run_build_with_repair_no_problem_id_returns_early(
    task_session, db, monkeypatch
):
    task_session.polygon_problem_id = None
    await db.commit()

    called = {"ensure": False}

    async def fake_ensure(db_, session):
        called["ensure"] = True

    _patch_session(monkeypatch, db)
    monkeypatch.setattr(repair, "ensure_files_loaded", fake_ensure)

    await repair.run_build_with_repair(task_session.id)
    assert called["ensure"] is False


@pytest.mark.asyncio
async def test_run_build_with_repair_happy_path(task_session, db, monkeypatch):
    task_session.problem_settings = {}
    task_session.examples = []
    await db.commit()

    steps = []
    apply_args = {}

    async def fake_ensure(db_, session):
        return None

    async def fake_build_and_poll(db_, session, *, scoring_groups=None, set_step):
        await set_step("Сборка пакета...")
        return {"status": "done", "package_id": 7, "group_map": {}}

    async def fake_apply(db_, sid, pid, progress, result):
        apply_args.update(result=result, progress=dict(progress), pid=pid)

    def fake_parse(scoring):
        return []

    _patch_session(monkeypatch, db)
    monkeypatch.setattr(repair, "ensure_files_loaded", fake_ensure)
    monkeypatch.setattr(repair.package_loop, "build_and_poll", fake_build_and_poll)
    monkeypatch.setattr(repair, "_apply_build_result", fake_apply)
    monkeypatch.setattr(repair, "parse_scoring_groups", fake_parse)

    await repair.run_build_with_repair(task_session.id)

    assert apply_args["result"]["status"] == "done"
    assert apply_args["pid"] == 555
    # the build stage was recorded on the session
    refreshed = await db.get(type(task_session), task_session.id)
    await db.refresh(refreshed)
    assert refreshed.stage == PipelineStage.BUILDING_PACKAGE


@pytest.mark.asyncio
async def test_run_build_with_repair_uploads_examples_and_groups(
    task_session, db, monkeypatch
):
    task_session.problem_settings = {"enable_groups": True, "subtasks": [{"group": "1"}]}
    task_session.examples = [{"input": "1", "output": "1"}]
    task_session.statement = {"scoring": "table"}
    await db.commit()

    upload_calls = {"n": 0, "group": None}
    setup_calls = {"n": 0}

    async def fake_ensure(db_, session):
        return None

    async def fake_upload_examples(db_, pid, uid, examples, group=None):
        upload_calls["n"] += 1
        upload_calls["group"] = group

    async def fake_setup(sid, pid, uid, settings, scoring, db_, subtasks=None):
        setup_calls["n"] += 1
        return [{"group": "1", "points": 100}]

    async def fake_build_and_poll(db_, session, *, scoring_groups=None, set_step):
        # groups were enabled → scoring_groups must be forwarded
        assert scoring_groups == [{"group": "1", "points": 100}]
        return {"status": "done", "package_id": 1, "group_map": {}}

    async def fake_apply(*a, **k):
        return None

    _patch_session(monkeypatch, db)
    monkeypatch.setattr(repair, "ensure_files_loaded", fake_ensure)
    monkeypatch.setattr(repair, "upload_examples", fake_upload_examples)
    monkeypatch.setattr(repair, "setup_groups_and_points", fake_setup)
    monkeypatch.setattr(repair.package_loop, "build_and_poll", fake_build_and_poll)
    monkeypatch.setattr(repair, "_apply_build_result", fake_apply)

    await repair.run_build_with_repair(task_session.id)

    assert upload_calls["n"] == 1
    assert upload_calls["group"] == "0"  # groups on → group "0" for samples
    assert setup_calls["n"] == 1


@pytest.mark.asyncio
async def test_run_build_with_repair_exception_sets_failed(
    task_session, db, monkeypatch
):
    task_session.problem_settings = {}
    task_session.examples = []
    await db.commit()

    async def fake_ensure(db_, session):
        return None

    async def fake_parse(scoring):
        raise AssertionError("not awaited")

    def fake_parse_sync(scoring):
        return []

    async def fake_build_and_poll(*a, **k):
        raise RuntimeError("kaboom")

    _patch_session(monkeypatch, db)
    monkeypatch.setattr(repair, "ensure_files_loaded", fake_ensure)
    monkeypatch.setattr(repair, "parse_scoring_groups", fake_parse_sync)
    monkeypatch.setattr(repair.package_loop, "build_and_poll", fake_build_and_poll)

    await repair.run_build_with_repair(task_session.id)

    refreshed = await db.get(type(task_session), task_session.id)
    await db.refresh(refreshed)
    assert refreshed.stage == PipelineStage.FAILED
    assert refreshed.progress["status"] == "failed"
    assert "kaboom" in refreshed.progress["error"]
