import logging

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt.crypt_password import hash_token
from api.pydantic_schemas import RefreshRequest, Token
from api.user.auth.base_auth import router as auth_router
from api.user.auth.tokens import get_tokens
from app.database import get_db
from models import RefreshToken

logger = logging.getLogger(__name__)


@auth_router.post("/refresh", response_model=Token)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    old_refresh_hash = hash_token(payload.refresh_token)

    _r = await db.execute(
        select(RefreshToken).filter_by(refresh_hash=old_refresh_hash)
    )
    db_token = _r.scalars().first()

    if not db_token:
        logger.warning("Token refresh failed: invalid refresh token")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    user_id = db_token.user_id
    session_id = str(db_token.id)

    access_token, refresh_token, created_at, expires_in = get_tokens(
        user_id, session_id
    )

    db_token.refresh_hash = hash_token(refresh_token)
    db_token.created_at = created_at
    db_token.expires_in = expires_in

    await db.commit()

    logger.debug(f"Token refreshed: user_id={user_id} session_id={session_id}")

    return Token(
        access_token=access_token, refresh_token=refresh_token, token_type="Bearer"
    )
