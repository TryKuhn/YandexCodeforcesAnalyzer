import logging
import uuid

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import hash_password, verify_password
from api.crypt.crypt_password import hash_token
from api.pydantic_schemas import Token, UserLogin, UserRegister
from api.user.auth.base_auth import router as auth_router
from api.user.auth.tokens import get_tokens
from api.user.auth.location import get_location
from app.database import get_db
from models import RefreshToken, Role, User

logger = logging.getLogger(__name__)


@auth_router.post("/register", response_model=Token)
async def register(
    payload: UserRegister, request: Request, db: AsyncSession = Depends(get_db)
):
    _r = await db.execute(select(User).filter_by(login=payload.login))
    user = _r.scalars().first()

    if user:
        logger.warning(f"Registration failed: login '{payload.login}' already exists")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this login already exists",
        )

    _r = await db.execute(select(Role).filter_by(name="Admin"))
    role = _r.scalars().first()

    if not role:
        logger.error("Registration failed: system role 'Admin' not found in DB")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Default system role "Admin" not found. Contact developer.',
        )

    hashed_password = hash_password(payload.password)

    new_user = User(
        login=payload.login,
        password=hashed_password,
        email=payload.email,
        role_id=role.id,
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    logger.info(f"New user registered: '{payload.login}' (id={new_user.id})")

    return await login(
        UserLogin(login=payload.login, password=payload.password),
        request=request,
        db=db,
    )


@auth_router.post("/login", response_model=Token)
async def login(
    payload: UserLogin, request: Request, db: AsyncSession = Depends(get_db)
) -> Token:
    client_ip = request.client.host if request.client else "unknown"

    _r = await db.execute(select(User).filter_by(login=payload.login))
    user = _r.scalars().first()

    if not user or not user.password:
        logger.warning(f"Login failed: unknown login '{payload.login}' from {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid login or password",
        )

    if not verify_password(payload.password, user.password):
        logger.warning(f"Login failed: wrong password for '{payload.login}' from {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid login or password",
        )

    user_id: int = user.id
    session_id = uuid.uuid4()

    location = await get_location(request.client.host if request.client else "unknown")
    user_agent = f'{location} | {request.headers.get("user-agent", "Unknown")}'

    access_token, refresh_token, created_at, expires_in = get_tokens(
        user_id, str(session_id)
    )

    refresh_hash = hash_token(refresh_token)

    refresh_token_sub = RefreshToken(
        id=session_id,
        refresh_hash=refresh_hash,
        user_id=user_id,
        user_agent=user_agent,
        created_at=created_at,
        expires_in=expires_in,
    )

    db.add(refresh_token_sub)
    await db.commit()

    logger.info(f"Login successful: user_id={user_id} ('{payload.login}') from {client_ip}")

    return Token(
        access_token=access_token, refresh_token=refresh_token, token_type="Bearer"
    )
