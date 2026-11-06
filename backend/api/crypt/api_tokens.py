"""Personal access tokens for the public API (``/api/public/v1``).

A token is ``tfp_`` + 40 random URL-safe characters. Only its sha256 is stored,
so a leaked database does not leak usable tokens. The two kinds of credentials
never mix: JWT routes reject these tokens (they are not JWTs) and
:func:`get_token_user` rejects JWTs (no ``tfp_`` prefix).
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from models.user.integrations import ApiToken

TOKEN_PREFIX = "tfp_"
# last_used_at is informative: do not write it on every request
TOUCH_INTERVAL = timedelta(minutes=5)

_bearer = HTTPBearer(auto_error=False)


def new_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(30)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def token_hint(token: str) -> str:
    return f"{token[:8]}…{token[-4:]}"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def get_token_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> int:
    """FastAPI dependency: the user id of a valid personal access token."""
    token = credentials.credentials if credentials else ""
    if not token.startswith(TOKEN_PREFIX):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="нужен персональный токен API (Authorization: Bearer tfp_…)",
        )
    row = (await db.execute(select(ApiToken).where(ApiToken.token_hash == token_hash(token)))).scalars().first()
    if row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="токен API недействителен или отозван")
    now = _utcnow()
    if row.last_used_at is None or now - row.last_used_at > TOUCH_INTERVAL:
        row.last_used_at = now
        await db.commit()
    return row.user_id
