"""Unit tests for the in-memory SessionStore (services.session_store)."""
import pytest

from api.user.gpt.services.session_store import SessionStore


@pytest.fixture(autouse=True)
def _clear_store():
    """Keep the class-level dict isolated between tests."""
    SessionStore._sessions.clear()
    yield
    SessionStore._sessions.clear()


def test_create_returns_unique_ids_and_stores_data():
    id1 = SessionStore.create({"a": 1})
    id2 = SessionStore.create({"b": 2})
    assert id1 != id2
    assert SessionStore.get(id1) == {"a": 1}
    assert SessionStore.get(id2) == {"b": 2}


def test_create_returns_uuid_string():
    sid = SessionStore.create({})
    import uuid
    # should not raise
    uuid.UUID(sid)


def test_get_missing_returns_none():
    assert SessionStore.get("nope") is None


def test_update_merges_into_existing():
    sid = SessionStore.create({"a": 1, "keep": True})
    SessionStore.update(sid, {"a": 2, "c": 3})
    assert SessionStore.get(sid) == {"a": 2, "keep": True, "c": 3}


def test_update_missing_is_noop():
    SessionStore.update("ghost", {"x": 1})
    assert SessionStore.get("ghost") is None
    assert "ghost" not in SessionStore._sessions


def test_delete_removes_entry():
    sid = SessionStore.create({"a": 1})
    SessionStore.delete(sid)
    assert SessionStore.get(sid) is None


def test_delete_missing_is_noop():
    # must not raise even when the id is absent
    SessionStore.delete("does-not-exist")
