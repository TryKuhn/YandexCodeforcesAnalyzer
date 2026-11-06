"""``/api/integrations/tokens``: personal access tokens for the public API.

The NlogN admin (or any other system) uses such a token to list the user's
problems and publish them (``/api/public/v1``). The token is shown once; only
its hash is kept.
"""
from __future__ import annotations

import logging

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.crypt.api_tokens import new_token, token_hash, token_hint
from api.user.integrations.base import integrations_router
from app.database import get_db
from models.user.integrations import ApiToken

logger = logging.getLogger(__name__)

MAX_TOKENS = 20


class TokenIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)


def _out(row: ApiToken) -> dict:
    return {
        "id": row.id,
        "name": row.name,
        "hint": row.token_hint,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
    }


async def _rows(user_id: int, db: AsyncSession) -> list[ApiToken]:
    return list((await db.execute(
        select(ApiToken).where(ApiToken.user_id == user_id).order_by(ApiToken.id)
    )).scalars().all())


@integrations_router.get("/tokens")
async def tokens_list(user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    return {"tokens": [_out(r) for r in await _rows(user_id, db)]}


@integrations_router.post("/tokens")
async def tokens_create(
    body: TokenIn, user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    """A new token; ``token`` is in this answer only."""
    if len(await _rows(user_id, db)) >= MAX_TOKENS:
        raise HTTPException(status_code=400, detail=f"не больше {MAX_TOKENS} токенов: отзовите ненужные")
    token = new_token()
    row = ApiToken(user_id=user_id, name=body.name.strip(), token_hash=token_hash(token), token_hint=token_hint(token))
    db.add(row)
    await db.commit()
    await db.refresh(row)
    logger.info("API token created: user_id=%s id=%s", user_id, row.id)
    return {**_out(row), "token": token}


@integrations_router.delete("/tokens/{token_id}")
async def tokens_revoke(
    token_id: int, user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    row = await db.get(ApiToken, token_id)
    if row is None or row.user_id != user_id:
        raise HTTPException(status_code=404, detail="токен не найден")
    await db.delete(row)
    await db.commit()
    return {"tokens": [_out(r) for r in await _rows(user_id, db)]}
