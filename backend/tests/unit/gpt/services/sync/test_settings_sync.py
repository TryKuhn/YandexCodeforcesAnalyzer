"""Unit tests for problem-settings / tags sync (services.sync.settings_sync)."""
import pytest

from api.user.gpt.services.sync import settings_sync as ss
from models.task.session import ProblemType


def _record(bucket, name):
    async def fake(*args, **kwargs):
        bucket.append((name, args, kwargs))
    return fake


def _patch(monkeypatch):
    calls = []
    for name in ("update_info", "set_tags", "commit_changes"):
        monkeypatch.setattr(
            f"api.user.gpt.services.sync.settings_sync.{name}",
            _record(calls, name),
        )
    return calls


# --------------------------------------------------------------------------- #
# sync_settings
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_sync_settings_pushes_info_and_commits(db, task_session, monkeypatch):
    calls = _patch(monkeypatch)
    settings = {
        "input_file": "in.txt", "output_file": "out.txt",
        "time_limit": 2000, "memory_limit": 256,
    }
    pid = await ss.sync_settings(db, task_session, settings)
    assert pid == 555

    info = [c for c in calls if c[0] == "update_info"][0]
    kwargs = info[2]
    assert kwargs["input_file_name"] == "in.txt"
    assert kwargs["output_file_name"] == "out.txt"
    assert kwargs["time_limit"] == 2000
    assert kwargs["memory_limit"] == 256
    # REGULAR session -> not interactive
    assert kwargs["interactive"] is False
    assert [c[0] for c in calls].count("commit_changes") == 1


@pytest.mark.asyncio
async def test_sync_settings_interactive_derived_from_problem_type(db, task_session, monkeypatch):
    calls = _patch(monkeypatch)
    task_session.problem_type = ProblemType.INTERACTIVE
    await db.commit()

    await ss.sync_settings(db, task_session, {})
    info = [c for c in calls if c[0] == "update_info"][0]
    assert info[2]["interactive"] is True


@pytest.mark.asyncio
async def test_sync_settings_no_commit(db, task_session, monkeypatch):
    calls = _patch(monkeypatch)
    await ss.sync_settings(db, task_session, {}, polygon_commit=False)
    assert "commit_changes" not in [c[0] for c in calls]


# --------------------------------------------------------------------------- #
# sync_tags
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_sync_tags_joins_and_commits(db, task_session, monkeypatch):
    calls = _patch(monkeypatch)
    pid = await ss.sync_tags(db, task_session, ["dp", "graphs"])
    assert pid == 555

    tags = [c for c in calls if c[0] == "set_tags"][0]
    # set_tags(problem_id, ",".join(tags), user_id, db)
    assert tags[1][0] == 555
    assert tags[1][1] == "dp,graphs"
    assert [c[0] for c in calls].count("commit_changes") == 1


@pytest.mark.asyncio
async def test_sync_tags_empty_skips_set_tags_and_commit(db, task_session, monkeypatch):
    calls = _patch(monkeypatch)
    pid = await ss.sync_tags(db, task_session, [])
    assert pid == 555
    assert calls == []


@pytest.mark.asyncio
async def test_sync_tags_no_commit(db, task_session, monkeypatch):
    calls = _patch(monkeypatch)
    await ss.sync_tags(db, task_session, ["x"], polygon_commit=False)
    names = [c[0] for c in calls]
    assert "set_tags" in names
    assert "commit_changes" not in names
