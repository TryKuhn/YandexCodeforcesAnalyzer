"""Unit tests for api/user/auth/change_password.py."""
import uuid
from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from api.crypt import hash_password, verify_password
from api.pydantic_schemas import ChangePassword
from api.user.auth.change_password import change_password
from models import RefreshToken, Role, User


async def _make_user_with_password(db, raw="OldPass1!"):
    role = Role(name="Plain")
    db.add(role)
    await db.flush()
    u = User(
        login="pwuser",
        password=hash_password(raw),
        email="pw@e.com",
        role_id=role.id,
    )
    db.add(u)
    await db.commit()
    await db.refresh(u)
    return u


async def _make_token(db, user):
    now = datetime(2026, 1, 1)
    tok = RefreshToken(
        id=uuid.uuid4(),
        refresh_hash=uuid.uuid4().hex,
        user_id=user.id,
        user_agent="UA",
        created_at=now,
        expires_in=now + timedelta(days=1),
    )
    db.add(tok)
    await db.commit()


@pytest.mark.asyncio
async def test_change_password_user_not_found_404(db):
    with pytest.raises(Exception) as exc:
        await change_password(
            ChangePassword(
                old_password="x", new_password="NewPass1!", confirm_password="NewPass1!"
            ),
            user_id=99999,
            db=db,
        )
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_change_password_wrong_old_400(db):
    u = await _make_user_with_password(db)
    with pytest.raises(Exception) as exc:
        await change_password(
            ChangePassword(
                old_password="WrongOld1!",
                new_password="NewPass1!",
                confirm_password="NewPass1!",
            ),
            user_id=u.id,
            db=db,
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_change_password_mismatch_confirm_400(db):
    u = await _make_user_with_password(db)
    with pytest.raises(Exception) as exc:
        await change_password(
            ChangePassword(
                old_password="OldPass1!",
                new_password="NewPass1!",
                confirm_password="Different1!",
            ),
            user_id=u.id,
            db=db,
        )
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_change_password_success_updates_and_clears_sessions(db):
    u = await _make_user_with_password(db)
    await _make_token(db, u)
    await _make_token(db, u)

    result = await change_password(
        ChangePassword(
            old_password="OldPass1!",
            new_password="NewPass1!",
            confirm_password="NewPass1!",
        ),
        user_id=u.id,
        db=db,
    )
    assert "successfully" in result["message"]

    refreshed = (
        (await db.execute(select(User).filter_by(id=u.id))).scalars().first()
    )
    assert verify_password("NewPass1!", refreshed.password)

    tokens = (
        (await db.execute(select(RefreshToken).filter_by(user_id=u.id)))
        .scalars()
        .all()
    )
    assert tokens == []  # all sessions invalidated
