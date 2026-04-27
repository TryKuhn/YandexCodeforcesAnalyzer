from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user, hash_password, verify_password
from api.pydantic_schemas import ChangePassword
from api.user.auth import auth_router
from app.database import get_db
from models import User


@auth_router.post("/change_password")
async def change_password(
    payload: ChangePassword,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user = await db.execute(select(User).filter_by(id=user_id))
    user = user.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
        )

    if not verify_password(payload.old_password, user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid password."
        )

    if payload.old_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password can't be the same.",
        )

    if payload.new_password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password and confirmation do not match.",
        )

    user.password = hash_password(payload.new_password)
    await db.commit()

    return {"message": "Successfully changed password."}
