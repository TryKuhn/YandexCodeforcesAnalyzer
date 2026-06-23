"""JWT creation/verification and FastAPI bearer-auth dependencies."""
from datetime import datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from settings import settings


def create_token(data: dict, created_at: datetime, expires_delta: int):
    """Encode a signed JWT from ``data`` with an ``exp`` ``expires_delta`` minutes after ``created_at``."""
    to_encode = data.copy()

    expire = created_at + timedelta(minutes=expires_delta)
    to_encode.update({"exp": int(expire.timestamp())})

    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )

    return encoded_jwt


def verify_token(token: str):
    """Decode and validate a JWT, returning its payload.

    Raises HTTP 401 for expired or otherwise invalid tokens.
    """
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired."
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        )


security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """FastAPI dependency that returns the ``user_id`` from a bearer token.

    Raises HTTP 401 when the token is invalid or lacks a user id.
    """
    token = credentials.credentials

    payload = verify_token(token)

    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User ID not found in token",
        )

    return user_id


def get_current_payload(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """FastAPI dependency that returns the full decoded JWT payload."""
    token = credentials.credentials

    payload = verify_token(token)

    return payload
