import logging

from fastapi import Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user, hash_password, verify_password
from api.pydantic_schemas import ChangePassword
from api.user.auth import auth_router
from app.database import get_db
from models import RefreshToken, User

logger = logging.getLogger(__name__)


@auth_router.post("/change_password")
async def change_password(
    payload: ChangePassword,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    _r = await db.execute(select(User).filter_by(id=user_id))
    user = _r.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if not verify_password(payload.old_password, user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid old password"
        )

    if payload.new_password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password and confirmation do not match",
        )

    user.password = hash_password(payload.new_password)

    # Invalidate all active sessions for security
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
    await db.commit()

    logger.info(f"Password changed: user_id={user_id}")
    return {"message": "Password changed successfully. Please login again."}
