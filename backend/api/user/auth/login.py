from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.api.crypt.password import hash_password, verify_password
from backend.api.crypt.token import create_token
from backend.api.pydantic_schemas.user.auth import UserRegister, UserLogin, Token

from backend.app.database import get_db

from backend.models.refresh_token import RefreshToken
from backend.models.user import User

from backend.settings import EXPIRES_ACCESS, EXPIRES_REFRESH

router = APIRouter()


@router.post('/register')
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

@router.post('/login')
async def login(payload: UserLogin, db: Session = Depends(get_db)):
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

    user_id: int = user_exists.id # type: ignore[assignment]
    created_at = datetime.now()
    expires_in = created_at + timedelta(minutes=EXPIRES_ACCESS)

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

    refresh_hash = hash_password(refresh_token)

    refresh_token_sub = RefreshToken(
        refresh_hash=refresh_hash,
        user_id=user_id,
        created_at=created_at,
        expires_in=expires_in,
    )

    db.add(refresh_token_sub)
    db.commit()

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type='bearer'
    )
