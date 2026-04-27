from fastapi import Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.crypt.crypt_password import hash_token
from api.pydantic_schemas import Token
from api.user.auth import auth_router
from app.database import get_db
from models import RefreshToken


@auth_router.post("/logout")
async def logout(payload: Token, db: AsyncSession = Depends(get_db)) -> dict:
    refresh_hash = hash_token(payload.refresh_token)

    db_token = await db.execute(
        select(RefreshToken).filter_by(refresh_hash=refresh_hash)
    )
    db_token = db_token.scalars().first()

    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token."
        )

    await db.delete(db_token)
    await db.commit()

    return {"message": "Successfully logged out."}


@auth_router.post("/logout_all")
async def logout_all(
    user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    await db.execute(delete(RefreshToken).where(RefreshToken.user_id == user_id))
    await db.commit()

    return {"message": "Successfully logged all devices out."}
