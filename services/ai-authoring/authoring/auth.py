"""Auth: the user's JWT (issued by the backend) and the tokens we mint for the backend.

The service shares ``SECRET_KEY`` with the backend. Incoming requests carry the
user's access token; background work (sync, builds) has no user request, so to
call the backend's Polygon routes on the user's behalf the service mints a
short-lived token with the same ``user_id`` claim plus ``svc`` to tell it apart.
"""
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from authoring.settings import settings

SERVICE_CLAIM = "ai-authoring"

_bearer = HTTPBearer()


def verify_token(token: str) -> dict:
    """Decode a JWT signed with the shared secret; 401 on any problem."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> int:
    """FastAPI dependency: the ``user_id`` of the bearer token."""
    payload = verify_token(credentials.credentials)
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User ID not found in token"
        )
    return int(user_id)


def mint_user_token(user_id: int, *, minutes: int | None = None) -> str:
    """A short-lived token for calling the backend as ``user_id``."""
    now = datetime.now(UTC)
    payload = {
        "user_id": user_id,
        "svc": SERVICE_CLAIM,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes or settings.SERVICE_TOKEN_MINUTES)).timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
