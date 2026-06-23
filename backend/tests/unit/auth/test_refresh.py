"""Unit tests for api/user/auth/refresh.py — token rotation handler."""
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from api.crypt.crypt_password import hash_token
from api.pydantic_schemas import RefreshRequest
from api.user.auth.refresh import refresh
from models import RefreshToken


async def _make_token(db, user, raw):
    now = datetime(2026, 1, 1)
    tok = RefreshToken(
        id=uuid.uuid4(),
        refresh_hash=hash_token(raw),
        user_id=user.id,
        user_agent="UA",
        created_at=now,
        expires_in=now + timedelta(days=1),
    )
    db.add(tok)
    await db.commit()
    await db.refresh(tok)
    return tok


@pytest.mark.asyncio
async def test_refresh_invalid_token_401(db):
    with pytest.raises(Exception) as exc:
        await refresh(RefreshRequest(refresh_token="nope"), db=db)
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_refresh_rotates_hash(db, user):
    tok = await _make_token(db, user, "old-raw")
    old_hash = tok.refresh_hash
    token_id = tok.id

    result = await refresh(RefreshRequest(refresh_token="old-raw"), db=db)
    assert result.token_type == "Bearer"
    assert result.access_token and result.refresh_token

    refreshed = (
        (await db.execute(select(RefreshToken).filter_by(id=token_id)))
        .scalars()
        .first()
    )
    # the stored hash must now match the NEW refresh token, not the old one
    assert refreshed.refresh_hash != old_hash
    assert refreshed.refresh_hash == hash_token(result.refresh_token)
