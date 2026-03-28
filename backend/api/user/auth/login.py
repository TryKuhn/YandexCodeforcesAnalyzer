from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.crypt import hash_password, verify_password
from api.pydantic_schemas import UserRegister, UserLogin, Token
from api.user.auth.tokens import get_tokens

from app.database import get_db

from models import RefreshToken, User

router = APIRouter()

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
