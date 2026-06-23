"""Unit tests for api/user/auth/logout.py — logout / logout_all handlers."""
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from api.crypt.crypt_password import hash_token
from api.pydantic_schemas import LogoutRequest
from api.user.auth.logout import logout, logout_all
from models import RefreshToken


async def _make_token(db, user, raw, **kw):
    now = datetime(2026, 1, 1)
    tok = RefreshToken(
        id=uuid.uuid4(),
        refresh_hash=hash_token(raw),
        user_id=user.id,
        user_agent="UA",
        created_at=now,
        expires_in=now + timedelta(days=1),
        **kw,
    )
    db.add(tok)
    await db.commit()
    return tok


@pytest.mark.asyncio
async def test_logout_invalid_token_400(db):
    with pytest.raises(Exception) as exc:
        await logout(LogoutRequest(refresh_token="nope"), db=db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_logout_success_deletes_token(db, user):
    await _make_token(db, user, "raw-refresh")
    result = await logout(LogoutRequest(refresh_token="raw-refresh"), db=db)
    assert result == {"message": "Logout successful!"}
    remaining = (await db.execute(select(RefreshToken))).scalars().all()
    assert remaining == []


@pytest.mark.asyncio
async def test_logout_all_invalid_token_400(db):
    with pytest.raises(Exception) as exc:
        await logout_all(LogoutRequest(refresh_token="nope"), db=db)
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_logout_all_deletes_every_user_session(db, user):
    await _make_token(db, user, "raw-1")
    await _make_token(db, user, "raw-2")
    await _make_token(db, user, "raw-3")
    result = await logout_all(LogoutRequest(refresh_token="raw-2"), db=db)
    assert result == {"message": "Logout all successful!"}
    remaining = (
        (await db.execute(select(RefreshToken).filter_by(user_id=user.id)))
        .scalars()
        .all()
    )
    assert remaining == []
