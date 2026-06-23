"""Unit tests for the lazy file loader (services.chat.file_context)."""
import pytest

from api.user.gpt.services.ai_file_helpers import (get_session_files,
                                                   upsert_ai_file)
from api.user.gpt.services.chat import file_context as fc

MOD = "api.user.gpt.services.chat.file_context"


@pytest.mark.asyncio
async def test_ensure_files_loaded_noop_when_files_present(db, task_session, monkeypatch):
    # Pre-populate statement so _ensure_statement returns early, and a file so the
    # loader short-circuits.
    task_session.statement = {"name": "x"}
    await upsert_ai_file(db, task_session.id, "checker", "code")
    await db.commit()

    called = {"load_all": False}

    async def fake_load_all(*a, **k):
        called["load_all"] = True
        return 0

    monkeypatch.setattr(f"{MOD}._load_all", fake_load_all)
    await fc.ensure_files_loaded(db, task_session)
    assert called["load_all"] is False


@pytest.mark.asyncio
async def test_ensure_files_loaded_noop_when_no_problem_id(db, task_session, monkeypatch):
    task_session.statement = {"name": "x"}
    task_session.polygon_problem_id = None
    await db.commit()

    called = {"load_all": False}

    async def fake_load_all(*a, **k):
        called["load_all"] = True
        return 0

    monkeypatch.setattr(f"{MOD}._load_all", fake_load_all)
    await fc.ensure_files_loaded(db, task_session)
    assert called["load_all"] is False


@pytest.mark.asyncio
async def test_ensure_files_loaded_pulls_from_polygon(db, task_session, monkeypatch):
    task_session.statement = {"name": "x"}  # skip statement load
    await db.commit()

    async def fake_load_all(db_, session):
        # simulate the loader writing a file into the session
        await upsert_ai_file(db_, session.id, "checker", "pulled", uploaded=True)
        await db_.commit()
        return 1

    monkeypatch.setattr(f"{MOD}._load_all", fake_load_all)
    await fc.ensure_files_loaded(db, task_session)

    files = await get_session_files(db, task_session.id)
    assert "checker" in files


@pytest.mark.asyncio
async def test_ensure_files_loaded_swallows_load_errors(db, task_session, monkeypatch):
    task_session.statement = {"name": "x"}
    await db.commit()

    async def boom(*a, **k):
        raise RuntimeError("polygon down")

    monkeypatch.setattr(f"{MOD}._load_all", boom)
    # must not raise
    await fc.ensure_files_loaded(db, task_session)


@pytest.mark.asyncio
async def test_ensure_statement_lazy_loads(db, task_session, monkeypatch):
    task_session.statement = None
    await db.commit()

    async def fake_get_statements(problem_id, user_id, db_):
        return {"raw": "data"}

    def fake_extract(raw):
        return {"name": "Loaded", "legend": "L"}

    monkeypatch.setattr(f"{MOD}.get_statements", fake_get_statements)
    monkeypatch.setattr(f"{MOD}._extract_statement", fake_extract)
    # prevent the file path from running real polygon calls
    async def fake_load_all(*a, **k):
        return 0
    monkeypatch.setattr(f"{MOD}._load_all", fake_load_all)

    await fc.ensure_files_loaded(db, task_session)
    assert task_session.statement == {"name": "Loaded", "legend": "L"}


@pytest.mark.asyncio
async def test_reload_from_polygon_no_problem_id(db, task_session):
    task_session.polygon_problem_id = None
    await db.commit()
    out = await fc.reload_from_polygon(db, task_session)
    assert out == {"files": 0, "statement": False}


@pytest.mark.asyncio
async def test_reload_from_polygon_loads_statement_and_files(db, task_session, monkeypatch):
    async def fake_get_statements(problem_id, user_id, db_):
        return {"raw": 1}

    def fake_extract(raw):
        return {"name": "R"}

    async def fake_load_all(db_, session):
        return 3

    monkeypatch.setattr(f"{MOD}.get_statements", fake_get_statements)
    monkeypatch.setattr(f"{MOD}._extract_statement", fake_extract)
    monkeypatch.setattr(f"{MOD}._load_all", fake_load_all)

    out = await fc.reload_from_polygon(db, task_session)
    assert out == {"files": 3, "statement": True}
    assert task_session.statement == {"name": "R"}
