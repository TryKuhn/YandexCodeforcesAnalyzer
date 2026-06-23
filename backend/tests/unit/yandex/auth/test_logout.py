"""Unit tests for api/user/yandex/auth/logout.py — logout_yandex handler."""
import pytest

from api.user.yandex.auth.logout import logout_yandex


@pytest.mark.asyncio
async def test_logout_clears_token(db, user):
    user.yandex_access_token = "TOK"
    await db.commit()

    result = await logout_yandex(user_id=user.id, db=db)

    assert result == {"message": "Yandex account logged out"}
    await db.refresh(user)
    assert user.yandex_access_token is None


@pytest.mark.asyncio
async def test_logout_idempotent_when_already_none(db, user):
    result = await logout_yandex(user_id=user.id, db=db)
    assert result == {"message": "Yandex account logged out"}
    await db.refresh(user)
    assert user.yandex_access_token is None
