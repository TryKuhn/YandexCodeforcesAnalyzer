"""Unit tests for api/user/polygon/auth/logout.py route handler."""
import pytest

from api.user.polygon.auth.logout import unlink_polygon


@pytest.mark.asyncio
async def test_unlink_polygon_clears_credentials(db, user):
    assert user.polygon_api_key == "key"
    result = await unlink_polygon(user_id=user.id, db=db)
    assert result == {"message": "Polygon account successfully unlinked"}

    await db.refresh(user)
    assert user.polygon_api_key is None
    assert user.polygon_api_secret is None


@pytest.mark.asyncio
async def test_unlink_polygon_missing_user_is_404(db):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        await unlink_polygon(user_id=999999, db=db)
    assert exc.value.status_code == 404
