"""Unit tests for api/user/codeforces/auth/logout.py — unlink_codeforces handler."""
import pytest

from api.user.codeforces.auth.logout import unlink_codeforces


@pytest.mark.asyncio
async def test_unlink_clears_credentials(db, user):
    # user fixture has polygon creds; give it CF creds too.
    user.codeforces_api_key = "K"
    user.codeforces_api_secret = "S"
    await db.commit()

    result = await unlink_codeforces(user_id=user.id, db=db)

    assert result == {"message": "Codeforces account successfully unlinked"}
    await db.refresh(user)
    assert user.codeforces_api_key is None
    assert user.codeforces_api_secret is None


@pytest.mark.asyncio
async def test_unlink_idempotent_when_already_none(db, user):
    result = await unlink_codeforces(user_id=user.id, db=db)
    assert result == {"message": "Codeforces account successfully unlinked"}
    await db.refresh(user)
    assert user.codeforces_api_key is None
