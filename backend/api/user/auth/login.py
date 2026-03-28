from datetime import datetime, timedelta, timezone
from typing import Tuple

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.pydantic_schemas.user.auth import Authorization
from api.crypt.password import hash_password, verify_password
from api.crypt.token import create_token, get_current_user
from api.pydantic_schemas.user.auth import UserRegister, UserLogin, Token, ChangePassword

from app.database import get_db

from models.user.refresh_token import RefreshToken
from models.user.user import User

from settings import EXPIRES_ACCESS, EXPIRES_REFRESH

router = APIRouter()


def get_tokens(user_id: int) -> Tuple[str, str, datetime, datetime]:
    created_at = datetime.now(timezone.utc)
    expires_in = created_at + timedelta(minutes=EXPIRES_REFRESH)

    data = {
        'user_id': user_id,
    }

    access_token = create_token(
        data=data,
        created_at=created_at,
        expires_delta=EXPIRES_ACCESS
    )

    refresh_token = create_token(
        data=data,
        created_at=created_at,
        expires_delta=EXPIRES_REFRESH
    )

    return access_token, refresh_token, created_at, expires_in


@router.post('/register', response_model=Token)
async def register(payload: UserRegister, db: Session = Depends(get_db)):
    user_exists = db.query(User).filter_by(login=payload.login).first()
    if user_exists:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='User with such login already exists.'
        )

    hashed_password = hash_password(payload.password)

    new_user = User(
        login=payload.login,
        password=hashed_password,
        email=payload.email,
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return await login(
        UserLogin(
            login=payload.login,
            password=payload.password
        ), db=db
    )


@router.post('/login', response_model=Token)
async def login(payload: UserLogin, db: Session = Depends(get_db)) -> Token:
    user_exists = db.query(User).filter_by(login=payload.login).first()
    if not user_exists:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid login or password.'
        )

    if not verify_password(payload.password, user_exists.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid login or password.'
        )

    user_id: int = user_exists.id  # type: ignore[assignment]

    access_token, refresh_token, created_at, expires_in = get_tokens(user_id)

    refresh_hash = hash_password(refresh_token)

    refresh_token_sub = RefreshToken(
        refresh_hash=refresh_hash,
        user_id=user_id,
        created_at=created_at,
        expires_in=expires_in
    )

    db.add(refresh_token_sub)
    db.commit()

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type='bearer'
    )


@router.post('/logout')
async def logout(payload: Token, db: Session = Depends(get_db)) -> dict:
    db_token = db.query(RefreshToken).filter_by(refresh_hash=hash_password(payload.refresh_token)).first()
    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid refresh token.'
        )

    db.delete(db_token)
    db.commit()

    return {'message': 'Successfully logged out.'}


@router.post('/logout_all')
async def logout_all(payload: Authorization, db: Session = Depends(get_db)) -> dict:
    user_id = get_current_user(payload.Authorization)

    db.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
    db.commit()

    return {'message': 'Successfully logged all.'}


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


@router.post('/change_password')
async def change_password(payload: ChangePassword, token: Token, db: Session = Depends(get_db)) -> dict:
    user_id = get_current_user(token.access_token)

    refresh_hash = hash_password(token.refresh_token)

    db_token = db.query(RefreshToken).filter_by(refresh_hash=refresh_hash).first()
    if not db_token or db_token.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    user = db.query(User).filter_by(id=user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='User not found.'
        )

    if not verify_password(payload.old_password, user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid password.'
        )

    if payload.old_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='New password can\'t be the same.'
        )

    if payload.new_password != payload.validate_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='New password and confirmation do not match.'
        )

    user.password = hash_password(payload.new_password)

    (db.query(RefreshToken).
     filter(RefreshToken.user_id == user.id, RefreshToken.refresh_hash != hash_password(token.refresh_token))
     .delete())

    db.commit()

    return {'message': 'Successfully changed password.'}
