"""Unit tests for the generated-file helpers (services.ai_file_helpers)."""
import pytest

from api.user.gpt.services import ai_file_helpers as H


def test_resolve_filename_mapped():
    assert H.resolve_filename("validator") == "validator.cpp"


def test_resolve_filename_custom_from_meta_adds_cpp():
    meta = {"sol_sub1": {"name": "sub1", "tag": "TL"}}
    assert H.resolve_filename("sol_sub1", meta) == "sub1.cpp"


def test_resolve_filename_custom_keeps_existing_extension():
    meta = {"x": {"name": "already.cpp"}}
    assert H.resolve_filename("x", meta) == "already.cpp"


def test_resolve_filename_unknown_falls_back_to_key():
    assert H.resolve_filename("mystery") == "mystery"


@pytest.mark.asyncio
async def test_upsert_inserts_then_updates(db, task_session):
    await H.upsert_ai_file(db, task_session.id, "validator", "v1")
    await db.commit()
    assert (await H.get_all_file_contents(db, task_session.id))["validator"] == "v1"

    await H.upsert_ai_file(db, task_session.id, "validator", "v2", uploaded=True)
    await db.commit()
    files = await H.get_session_files(db, task_session.id)
    assert files["validator"].content == "v2" and files["validator"].uploaded is True


@pytest.mark.asyncio
async def test_upsert_all_skips_empty(db, task_session):
    await H.upsert_all_ai_files(db, task_session.id, {"checker": "c", "empty": ""})
    await db.commit()
    keys = (await H.get_all_file_contents(db, task_session.id)).keys()
    assert "checker" in keys and "empty" not in keys


@pytest.mark.asyncio
async def test_mark_uploaded_and_uploaded_contents(db, task_session):
    await H.upsert_ai_file(db, task_session.id, "checker", "c")
    await db.commit()
    assert await H.get_uploaded_file_contents(db, task_session.id) == {}

    await H.mark_uploaded(db, task_session.id, "checker")
    await db.commit()
    assert await H.get_uploaded_file_contents(db, task_session.id) == {"checker": "c"}
