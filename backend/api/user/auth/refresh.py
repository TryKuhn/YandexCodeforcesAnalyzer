import uuid

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt.crypt_password import hash_token
from api.pydantic_schemas import Token
from api.user.auth import auth_router, get_tokens
from app.database import get_db
from models import RefreshToken


@auth_router.post("/refresh", response_model=Token)
async def refresh(payload: Token, db: AsyncSession = Depends(get_db)):
    old_refresh_hash = hash_token(payload.refresh_token)

    db_token = await db.execute(
        select(RefreshToken).filter_by(refresh_hash=old_refresh_hash)
    )
    db_token = db_token.scalars().first()

    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token."
        )

    new_sid = uuid.uuid4()
    user_id = db_token.user_id

    access_token, refresh_token, created_at, expires_in = get_tokens(
        user_id, str(new_sid)
    )

    new_refresh_hash = hash_token(refresh_token)

    db_token.id = new_sid
    db_token.refresh_hash = new_refresh_hash
    db_token.created_at = created_at
    db_token.expires_in = expires_in

    await db.commit()

    return Token(
        access_token=access_token, refresh_token=refresh_token, token_type="Bearer"
    )
