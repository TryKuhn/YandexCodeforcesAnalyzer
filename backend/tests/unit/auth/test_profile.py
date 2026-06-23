"""Unit tests for api/user/auth/profile.py — get_me / get_sessions handlers."""
import uuid
from datetime import datetime, timedelta

import pytest

from api.user.auth.profile import get_me, get_sessions
from models import RefreshToken


async def _make_token(db, user, raw_id=None):
    now = datetime(2026, 1, 1)
    tok = RefreshToken(
        id=raw_id or uuid.uuid4(),
        refresh_hash=uuid.uuid4().hex,
        user_id=user.id,
        user_agent="UA",
        last_seen=now,
        created_at=now,
        expires_in=now + timedelta(days=1),
    )
    db.add(tok)
    await db.commit()
    await db.refresh(tok)
    return tok


# --------------------------------------------------------------------------- #
# get_me
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_me_not_found_404(db):
    with pytest.raises(Exception) as exc:
        await get_me(user_id=99999, db=db)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_get_me_returns_link_flags(db, user):
    result = await get_me(user_id=user.id, db=db)
    assert result["id"] == user.id
    assert result["login"] == "tester"
    assert result["email"] == "tester@example.com"
    # user fixture sets polygon creds but not yandex/codeforces
    assert result["is_polygon_linked"] is True
    assert result["is_yandex_linked"] is False
    assert result["is_codeforces_linked"] is False


# --------------------------------------------------------------------------- #
# get_sessions
# --------------------------------------------------------------------------- #
@pytest.mark.asyncio
async def test_get_sessions_empty(db, user):
    result = await get_sessions(
        payload={"user_id": user.id, "sid": "none"}, db=db
    )
    assert result == []


@pytest.mark.asyncio
async def test_get_sessions_marks_current(db, user):
    current = await _make_token(db, user)
    await _make_token(db, user)

    result = await get_sessions(
        payload={"user_id": user.id, "sid": str(current.id)}, db=db
    )
    assert len(result) == 2
    current_rows = [r for r in result if r["is_current"]]
    assert len(current_rows) == 1
    assert str(current_rows[0]["id"]) == str(current.id)
    # timestamps are isoformat + "Z"
    assert current_rows[0]["created_at"].endswith("Z")
    assert current_rows[0]["last_seen"].endswith("Z")
