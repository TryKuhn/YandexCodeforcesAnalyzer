"""Flow tests for the full build pipeline (services.build.pipeline).

Covers _apply_build_result, _upload_examples, _upload_tech_files and the
run_full_build orchestrator with all Polygon/AI collaborators mocked.
"""
import pytest

from api.user.gpt.services.build import pipeline
from models.task.session import PipelineStage, ProblemType


class _FakeSessionCtx:
    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, *exc):
        return False


def _patch_session(monkeypatch, db):
    monkeypatch.setattr(pipeline, "Session", lambda: _FakeSessionCtx(db))


async def _noop(*a, **k):
    return None


# --------------------------------------------------------------------------- #
# _apply_build_result
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_apply_build_result_done_sets_done_stage(task_session, db):
    progress = {"status": "building"}
    result = {"status": "done", "package_id": 88, "group_map": {"1": [2, 3]}}

    await pipeline._apply_build_result(db, task_session.id, 555, progress, result)

    refreshed = await db.get(type(task_session), task_session.id)
    await db.refresh(refreshed)
    assert refreshed.stage == PipelineStage.DONE
    assert refreshed.package_id == 88
    # group distribution gets written into the chat log
    assert refreshed.chat_log
    assert any("Группа 1" in m["content"] for m in refreshed.chat_log)


@pytest.mark.asyncio
async def test_apply_build_result_done_no_groups(task_session, db):
    progress = {"status": "building"}
    result = {"status": "done", "package_id": 5}

    await pipeline._apply_build_result(db, task_session.id, 555, progress, result)

    refreshed = await db.get(type(task_session), task_session.id)
    await db.refresh(refreshed)
    assert refreshed.stage == PipelineStage.DONE
    # chat log present but without a group-distribution section
    assert refreshed.chat_log
    assert all("Распределение" not in m["content"] for m in refreshed.chat_log)


@pytest.mark.asyncio
async def test_apply_build_result_manual_fix_escalates(task_session, db):
    progress = {"status": "building"}
    result = {"status": "manual_fix", "offender": "checker", "error": "bad checker"}

    await pipeline._apply_build_result(db, task_session.id, 555, progress, result)

    refreshed = await db.get(type(task_session), task_session.id)
    await db.refresh(refreshed)
    assert refreshed.stage == PipelineStage.FIXING_ERRORS
    assert refreshed.progress["status"] == "waiting_manual_fix"
    assert refreshed.upload_errors["package"]["error"] == "bad checker"
    assert refreshed.upload_errors["checker"]["needs_manual_fix"] is True


@pytest.mark.asyncio
async def test_apply_build_result_timeout_escalates_without_offender(
    task_session, db
):
    progress = {"status": "building"}
    result = {"status": "timeout", "error": "build timed out"}

    await pipeline._apply_build_result(db, task_session.id, 555, progress, result)

    refreshed = await db.get(type(task_session), task_session.id)
    await db.refresh(refreshed)
    assert refreshed.stage == PipelineStage.FIXING_ERRORS
    assert "checker" not in (refreshed.upload_errors or {})
    assert refreshed.upload_errors["package"]["error"] == "build timed out"


# --------------------------------------------------------------------------- #
# _upload_examples
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_upload_examples_saves_each_with_index(monkeypatch):
    saved = []

    async def fake_save_test(**k):
        saved.append(k)

    monkeypatch.setattr(pipeline, "save_test", fake_save_test)

    examples = [{"input": "a"}, {"input": "b"}]
    await pipeline._upload_examples(555, 1, examples, None)

    assert [s["test_index"] for s in saved] == [1, 2]
    assert [s["test_input"] for s in saved] == ["a", "b"]
    assert all(s["test_use_in_statements"] for s in saved)


@pytest.mark.asyncio
async def test_upload_examples_swallows_individual_failure(monkeypatch):
    saved = []

    async def fake_save_test(**k):
        if k["test_index"] == 1:
            raise RuntimeError("boom on first")
        saved.append(k)

    monkeypatch.setattr(pipeline, "save_test", fake_save_test)

    await pipeline._upload_examples(555, 1, [{"input": "a"}, {"input": "b"}], None)
    # second test still saved despite first failing
    assert [s["test_index"] for s in saved] == [2]


# --------------------------------------------------------------------------- #
# _upload_tech_files
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_upload_tech_files_uploads_present_files(task_session, db, monkeypatch):
    synced = []

    async def fake_contents(db_, sid):
        # only validator present among applicable types
        return {"validator": "VALIDATOR_CODE"}

    async def fake_sync_file(db_, session, ft, code, polygon_commit=False):
        synced.append((ft, code))

    monkeypatch.setattr(pipeline, "get_all_file_contents", fake_contents)
    monkeypatch.setattr(pipeline, "sync_file", fake_sync_file)

    errors = await pipeline._upload_tech_files(db, task_session, {}, _noop)
    assert errors == {}
    assert synced == [("validator", "VALIDATOR_CODE")]


@pytest.mark.asyncio
async def test_upload_tech_files_retries_then_fixes(task_session, db, monkeypatch):
    async def fake_contents(db_, sid):
        return {"validator": "BAD"}

    attempts = {"n": 0}

    async def fake_sync_file(db_, session, ft, code, polygon_commit=False):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("first upload fails")
        # second attempt with fixed code succeeds

    fixed_calls = {"n": 0}

    async def fake_fix(file_type, code, err, statement, model,
                       previous_errors=None):
        fixed_calls["n"] += 1
        return "GOOD"

    monkeypatch.setattr(pipeline, "get_all_file_contents", fake_contents)
    monkeypatch.setattr(pipeline, "sync_file", fake_sync_file)
    monkeypatch.setattr(pipeline.fix_gen, "fix", fake_fix)

    errors = await pipeline._upload_tech_files(db, task_session, {}, _noop)
    assert errors == {}
    assert fixed_calls["n"] == 1
    assert attempts["n"] == 2


@pytest.mark.asyncio
async def test_upload_tech_files_exhausts_retries_records_error(
    task_session, db, monkeypatch
):
    async def fake_contents(db_, sid):
        return {"validator": "BAD"}

    async def fake_sync_file(*a, **k):
        raise RuntimeError("always fails")

    async def fake_fix(*a, **k):
        return "still bad"

    monkeypatch.setattr(pipeline, "get_all_file_contents", fake_contents)
    monkeypatch.setattr(pipeline, "sync_file", fake_sync_file)
    monkeypatch.setattr(pipeline.fix_gen, "fix", fake_fix)

    errors = await pipeline._upload_tech_files(db, task_session, {}, _noop)
    assert "validator" in errors
    assert errors["validator"]["needs_manual_fix"] is True
    assert errors["validator"]["error"] == "always fails"


# --------------------------------------------------------------------------- #
# run_full_build
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_run_full_build_missing_session_returns(monkeypatch, db):
    _patch_session(monkeypatch, db)
    # no session with this id exists → should return without error
    await pipeline.run_full_build("does-not-exist")


@pytest.mark.asyncio
async def test_run_full_build_orchestrates_all_steps(task_session, db, monkeypatch):
    task_session.statement = {"name": "P", "scoring": None}
    task_session.problem_settings = {"tags": ["math"]}
    task_session.examples = [{"input": "1"}]
    await db.commit()

    order = []

    async def fake_ensure_problem(db_, session):
        order.append("ensure_problem")
        return 555

    async def fake_sync_settings(db_, session, settings, polygon_commit=False):
        order.append("sync_settings")

    async def fake_sync_statement(db_, session, statement, polygon_commit=False):
        order.append("sync_statement")

    async def fake_upload_examples(pid, uid, examples, db_):
        order.append("upload_examples")

    async def fake_sync_tags(db_, session, tags, polygon_commit=False):
        order.append("sync_tags")

    async def fake_setup(*a, **k):
        order.append("setup_groups")
        return [{"group": "1"}]

    async def fake_upload_tech(db_, session, statement, set_step):
        order.append("upload_tech")
        return {}

    async def fake_commit(*a, **k):
        order.append("commit")

    async def fake_build_and_poll(db_, session, *, scoring_groups=None, set_step):
        order.append("build_and_poll")
        assert scoring_groups == [{"group": "1"}]
        return {"status": "done", "package_id": 9, "group_map": {}}

    applied = {}

    async def fake_apply(db_, sid, pid, progress, result):
        order.append("apply")
        applied.update(result=result, pid=pid)

    _patch_session(monkeypatch, db)
    monkeypatch.setattr(pipeline, "ensure_problem", fake_ensure_problem)
    monkeypatch.setattr(pipeline, "sync_settings", fake_sync_settings)
    monkeypatch.setattr(pipeline, "sync_statement", fake_sync_statement)
    monkeypatch.setattr(pipeline, "_upload_examples", fake_upload_examples)
    monkeypatch.setattr(pipeline, "sync_tags", fake_sync_tags)
    monkeypatch.setattr(pipeline, "setup_groups_and_points", fake_setup)
    monkeypatch.setattr(pipeline, "_upload_tech_files", fake_upload_tech)
    monkeypatch.setattr(pipeline, "commit_changes", fake_commit)
    monkeypatch.setattr(pipeline.package_loop, "build_and_poll", fake_build_and_poll)
    monkeypatch.setattr(pipeline, "_apply_build_result", fake_apply)

    await pipeline.run_full_build(task_session.id)

    assert order == [
        "ensure_problem", "sync_settings", "sync_statement", "upload_examples",
        "sync_tags", "setup_groups", "upload_tech", "commit", "build_and_poll",
        "apply",
    ]
    assert applied["result"]["status"] == "done"
    assert applied["pid"] == 555


@pytest.mark.asyncio
async def test_run_full_build_output_only_forces_points(task_session, db, monkeypatch):
    task_session.problem_type = ProblemType.OUTPUT_ONLY
    task_session.statement = {}
    task_session.problem_settings = {}
    task_session.examples = []
    await db.commit()

    captured = {}

    async def fake_ensure_problem(db_, session):
        return 555

    async def fake_setup(sid, pid, uid, settings, scoring, db_, subtasks=None):
        captured["enable_points"] = settings.get("enable_points")
        return []

    async def fake_upload_tech(*a, **k):
        return {}

    async def fake_build_and_poll(*a, **k):
        return {"status": "done", "package_id": 1, "group_map": {}}

    _patch_session(monkeypatch, db)
    monkeypatch.setattr(pipeline, "ensure_problem", fake_ensure_problem)
    monkeypatch.setattr(pipeline, "sync_settings", _noop)
    monkeypatch.setattr(pipeline, "sync_statement", _noop)
    monkeypatch.setattr(pipeline, "setup_groups_and_points", fake_setup)
    monkeypatch.setattr(pipeline, "_upload_tech_files", fake_upload_tech)
    monkeypatch.setattr(pipeline, "commit_changes", _noop)
    monkeypatch.setattr(pipeline.package_loop, "build_and_poll", fake_build_and_poll)
    monkeypatch.setattr(pipeline, "_apply_build_result", _noop)

    await pipeline.run_full_build(task_session.id)
    assert captured["enable_points"] is True


@pytest.mark.asyncio
async def test_run_full_build_records_upload_errors(task_session, db, monkeypatch):
    task_session.statement = {}
    task_session.problem_settings = {}
    task_session.examples = []
    await db.commit()

    async def fake_ensure_problem(db_, session):
        return 555

    async def fake_upload_tech(*a, **k):
        return {"validator": {"error": "boom", "needs_manual_fix": True}}

    async def fake_build_and_poll(*a, **k):
        return {"status": "done", "package_id": 1, "group_map": {}}

    _patch_session(monkeypatch, db)
    monkeypatch.setattr(pipeline, "ensure_problem", fake_ensure_problem)
    monkeypatch.setattr(pipeline, "sync_settings", _noop)
    monkeypatch.setattr(pipeline, "sync_statement", _noop)
    monkeypatch.setattr(pipeline, "setup_groups_and_points",
                        lambda *a, **k: _noop())

    async def fake_setup(*a, **k):
        return []

    monkeypatch.setattr(pipeline, "setup_groups_and_points", fake_setup)
    monkeypatch.setattr(pipeline, "_upload_tech_files", fake_upload_tech)
    monkeypatch.setattr(pipeline, "commit_changes", _noop)
    monkeypatch.setattr(pipeline.package_loop, "build_and_poll", fake_build_and_poll)
    monkeypatch.setattr(pipeline, "_apply_build_result", _noop)

    await pipeline.run_full_build(task_session.id)

    refreshed = await db.get(type(task_session), task_session.id)
    await db.refresh(refreshed)
    assert refreshed.upload_errors["validator"]["error"] == "boom"


@pytest.mark.asyncio
async def test_run_full_build_exception_sets_failed(task_session, db, monkeypatch):
    task_session.statement = {}
    task_session.problem_settings = {}
    task_session.examples = []
    await db.commit()

    async def fake_ensure_problem(*a, **k):
        raise RuntimeError("explode")

    _patch_session(monkeypatch, db)
    monkeypatch.setattr(pipeline, "ensure_problem", fake_ensure_problem)

    await pipeline.run_full_build(task_session.id)

    refreshed = await db.get(type(task_session), task_session.id)
    await db.refresh(refreshed)
    assert refreshed.stage == PipelineStage.FAILED
    assert refreshed.progress["status"] == "failed"
    assert "explode" in refreshed.progress["error"]
