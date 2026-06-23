"""Unit tests for the single-file Polygon sync (services.sync.file_sync)."""
import pytest

from api.user.gpt.services.sync import file_sync as fs
from api.user.gpt.services.ai_file_helpers import (get_all_file_contents,
                                                   get_session_files)


def _record(bucket, name):
    """Build an async fake that appends its call to ``bucket`` keyed by ``name``."""
    async def fake(*args, **kwargs):
        bucket.append((name, args, kwargs))
    return fake


def _patch_setters(monkeypatch):
    """Replace every Polygon setter + commit in the module with recording fakes.

    Returns the shared ``calls`` list of (name, args, kwargs) tuples.
    """
    calls = []
    for name in (
        "set_validator", "set_generator", "set_checker", "set_interactor",
        "save_script", "save_solution", "commit_changes",
    ):
        monkeypatch.setattr(f"api.user.gpt.services.sync.file_sync.{name}",
                            _record(calls, name))
    return calls


# --------------------------------------------------------------------------- #
# _make_polygon_name
# --------------------------------------------------------------------------- #
def test_make_polygon_name_shape():
    name = fs._make_polygon_name("anthropic/claude-opus-4.8", "sess-1234")
    # model_short strips non-alnum and truncates to 8 chars: "claudeop"
    assert name.startswith("claudeop-task-sess-")
    parts = name.split("-")
    # claudeop / task / sess / <suffix-rest> ... last chunk is the timestamp
    assert "task" in parts
    assert name.split("-task-")[1].startswith("sess")


def test_make_polygon_name_handles_blank_model():
    name = fs._make_polygon_name("", "abcd")
    assert name.startswith("ai-task-abcd-")


# --------------------------------------------------------------------------- #
# ensure_problem
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_ensure_problem_returns_existing_id(db, task_session, monkeypatch):
    created = []
    monkeypatch.setattr(
        "api.user.gpt.services.sync.file_sync.create_problem",
        _record(created, "create"),
    )
    # task_session has polygon_problem_id=555
    assert await fs.ensure_problem(db, task_session) == 555
    assert created == []


@pytest.mark.asyncio
async def test_ensure_problem_creates_when_missing(db, task_session, monkeypatch):
    task_session.polygon_problem_id = None
    await db.commit()

    async def fake_create_problem(name, user_id, db):
        return 999

    monkeypatch.setattr(
        "api.user.gpt.services.sync.file_sync.create_problem", fake_create_problem
    )
    pid = await fs.ensure_problem(db, task_session)
    assert pid == 999
    assert task_session.polygon_problem_id == 999


# --------------------------------------------------------------------------- #
# _push_to_polygon routing
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
@pytest.mark.parametrize(
    "category,expected",
    [
        ("validator", "set_validator"),
        ("generator", "set_generator"),
        ("checker", "set_checker"),
        ("interactor", "set_interactor"),
        ("script", "save_script"),
        ("solution", "save_solution"),
    ],
)
async def test_push_to_polygon_routes_by_category(monkeypatch, category, expected):
    calls = _patch_setters(monkeypatch)
    await fs._push_to_polygon(category, 1, "f.cpp", "code", "OK", 7, None)
    assert [c[0] for c in calls] == [expected]


@pytest.mark.asyncio
async def test_push_to_polygon_script_uses_tests_testset(monkeypatch):
    calls = _patch_setters(monkeypatch)
    await fs._push_to_polygon("script", 1, "script.txt", "gen 1 2", None, 7, None)
    name, args, _ = calls[0]
    # save_script(problem_id, "tests", content, user_id, db)
    assert args[0] == 1 and args[1] == "tests" and args[2] == "gen 1 2"


@pytest.mark.asyncio
async def test_push_to_polygon_solution_forwards_tag(monkeypatch):
    calls = _patch_setters(monkeypatch)
    await fs._push_to_polygon("solution", 1, "wa.cpp", "code", "WA", 7, None)
    name, args, _ = calls[0]
    # save_solution(problem_id, filename, content, tag, user_id, db)
    assert args[3] == "WA"


@pytest.mark.asyncio
async def test_push_to_polygon_unknown_category_raises(monkeypatch):
    _patch_setters(monkeypatch)
    with pytest.raises(ValueError):
        await fs._push_to_polygon("mystery", 1, "f", "c", None, 7, None)


# --------------------------------------------------------------------------- #
# sync_file
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_sync_file_upserts_marks_uploaded_and_routes(db, task_session, monkeypatch):
    calls = _patch_setters(monkeypatch)

    filename = await fs.sync_file(db, task_session, "validator", "int main(){}")
    assert filename == "validator.cpp"

    # routed to set_validator + committed Polygon working copy
    names = [c[0] for c in calls]
    assert "set_validator" in names
    assert "commit_changes" in names

    # local row persisted + marked uploaded
    files = await get_session_files(db, task_session.id)
    assert files["validator"].content == "int main(){}"
    assert files["validator"].uploaded is True


@pytest.mark.asyncio
async def test_sync_file_no_commit_skips_commit_changes(db, task_session, monkeypatch):
    calls = _patch_setters(monkeypatch)
    await fs.sync_file(db, task_session, "checker", "chk", polygon_commit=False)
    names = [c[0] for c in calls]
    assert "set_checker" in names
    assert "commit_changes" not in names


@pytest.mark.asyncio
async def test_sync_file_custom_solution_uses_solution_meta(db, task_session, monkeypatch):
    calls = _patch_setters(monkeypatch)
    task_session.solution_meta = {"sol_custom_1": {"name": "brute", "tag": "TL"}}
    await db.commit()

    filename = await fs.sync_file(db, task_session, "sol_custom_1", "brute code")
    assert filename == "brute.cpp"

    # not in registry -> routed as solution with the meta tag
    save = [c for c in calls if c[0] == "save_solution"][0]
    # save_solution(problem_id, filename, content, tag, user_id, db)
    assert save[1][3] == "TL"


# --------------------------------------------------------------------------- #
# sync_files (batch)
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_sync_files_batch_skips_empty_and_commits_once(db, task_session, monkeypatch):
    calls = _patch_setters(monkeypatch)
    synced = await fs.sync_files(
        db, task_session,
        [("validator", "v"), ("checker", ""), ("solution_cpp", "s")],
    )
    assert synced == ["validator", "solution_cpp"]
    # exactly one batch commit at the end
    assert [c[0] for c in calls].count("commit_changes") == 1


@pytest.mark.asyncio
async def test_sync_files_resilient_to_one_failure(db, task_session, monkeypatch):
    _patch_setters(monkeypatch)

    real_push = fs._push_to_polygon

    async def flaky_push(category, *args, **kwargs):
        if category == "validator":
            raise RuntimeError("polygon down")
        return await real_push(category, *args, **kwargs)

    monkeypatch.setattr(
        "api.user.gpt.services.sync.file_sync._push_to_polygon", flaky_push
    )

    synced = await fs.sync_files(
        db, task_session, [("validator", "v"), ("checker", "c")]
    )
    # validator failed and was skipped, checker still synced
    assert synced == ["checker"]
    contents = await get_all_file_contents(db, task_session.id)
    # both rows upserted (upsert happens before push), but only checker uploaded
    files = await get_session_files(db, task_session.id)
    assert files["validator"].uploaded is False
    assert files["checker"].uploaded is True
