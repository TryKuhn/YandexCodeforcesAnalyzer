"""Logout endpoints: revoke a single session or all of a user's sessions."""
import logging

from fastapi import Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt.crypt_password import hash_token
from api.pydantic_schemas import LogoutRequest
from api.user.auth.base_auth import router as auth_router
from app.database import get_db
from models import RefreshToken

logger = logging.getLogger(__name__)


@auth_router.post("/logout")
async def logout(payload: LogoutRequest, db: AsyncSession = Depends(get_db)) -> dict:
    """Revoke the single session identified by the given refresh token."""
    refresh_hash = hash_token(payload.refresh_token)

    _r = await db.execute(select(RefreshToken).filter_by(refresh_hash=refresh_hash))
    db_token = _r.scalars().first()

    if not db_token:
        logger.warning("Logout failed: invalid refresh token")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid refresh token"
        )

    user_id = db_token.user_id
    await db.delete(db_token)
    await db.commit()

    logger.info(f"Logout: user_id={user_id}")
    return {"message": "Logout successful!"}


@auth_router.post("/logout_all")
async def logout_all(
    payload: LogoutRequest, db: AsyncSession = Depends(get_db)
) -> dict:
    """Revoke every session for the user owning the given refresh token."""
    refresh_hash = hash_token(payload.refresh_token)

    _r = await db.execute(select(RefreshToken).filter_by(refresh_hash=refresh_hash))
    db_token = _r.scalars().first()

    if not db_token:
        logger.warning("Logout-all failed: invalid refresh token")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid refresh token"
        )

    user_id = db_token.user_id
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
    await db.commit()

    logger.info(f"Logout all sessions: user_id={user_id}")
    return {"message": "Logout all successful!"}
