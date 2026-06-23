"""Endpoint for linking a user's Codeforces API credentials."""
import logging
from time import time

from aiohttp import ClientSession
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yarl import URL

from api.crypt import get_current_user
from api.pydantic_schemas import LinkCodeforces
from api.user.codeforces.base_codeforces import router as codeforces_router
from api.user.codeforces.create_signature import create_signature
from api.user.codeforces.get_response import get_response
from app.database import get_db
from models import User
from settings import settings

logger = logging.getLogger(__name__)


@codeforces_router.post("/link")
async def link_codeforces(
    payload: LinkCodeforces,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Validate and store the user's Codeforces API key/secret.

    Credentials are verified by calling the authenticated ``user.friends``
    method, which fails for invalid key/secret pairs; only valid credentials
    are persisted.
    """
    user = await db.execute(select(User).filter_by(id=user_id))
    user = user.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    method_name = "user.friends"
    params = {
        "apiKey": payload.api_key,
        "time": str(int(time())),
        "onlyOnline": "false",
    }
    signature = await create_signature(method_name, params, payload.api_secret)
    params["apiSig"] = signature
    url = URL(settings.CODEFORCES_HOST) / method_name

    try:
        async with ClientSession() as client:
            await get_response(client, url, params)
    except HTTPException as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Codeforces credentials: {e.detail}",
        )
    except Exception as e:
        logger.error(f"Codeforces validation network error for user_id={user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to connect to Codeforces API",
        )

    user.codeforces_api_key = payload.api_key
    user.codeforces_api_secret = payload.api_secret
    await db.commit()

    logger.info(f"Codeforces API key linked: user_id={user_id}")
    return {"message": "Codeforces account successfully linked"}
