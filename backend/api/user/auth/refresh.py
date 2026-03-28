from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.crypt import hash_password
from api.pydantic_schemas import Token
from api.user.auth.login import get_tokens
from app.database import get_db
from models import RefreshToken

router = APIRouter()

@router.post('/refresh', response_model=Token)
async def refresh(payload: Token, db: Session = Depends(get_db)):
    db_token = db.query(RefreshToken).filter_by(refresh_hash=hash_password(payload.refresh_token)).first()
    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid refresh token.'
        )

    user_id: int = db_token.user_id  # type: ignore[assignment]

    access_token, refresh_token, created_at, expires_in = get_tokens(user_id)

    refresh_hash = hash_password(refresh_token)

    refresh_token_sub = RefreshToken(
        refresh_hash=refresh_hash,
        user_id=user_id,
        created_at=created_at,
        expires_in=expires_in
    )

    db.add(refresh_token_sub)
    db.flush()

    db.delete(db_token)
    db.commit()

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type='bearer'
    )