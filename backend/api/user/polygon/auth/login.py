"""Link a user's Polygon API credentials after probing them for validity."""
import logging
from time import time

from aiohttp import ClientSession
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yarl import URL

from api.crypt import get_current_user
from api.pydantic_schemas import LinkCodeforces
from api.user.polygon.base_polygon import polygon_router
from api.user.polygon.create_signature import create_signature
from api.user.polygon.get_response import PolygonAPIError, get_response
from app.database import get_db
from models import User
from settings import settings

logger = logging.getLogger(__name__)


@polygon_router.post("/link")
async def link_polygon(
    payload: LinkCodeforces,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Validate and store the user's Polygon API credentials.

    Probes Polygon's ``problems.list`` with a freshly signed request to verify
    the supplied key/secret before persisting them on the user. Returns 400 on
    invalid credentials and 502 if Polygon cannot be reached."""
    _r = await db.execute(select(User).filter_by(id=user_id))
    user = _r.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    method_name = "problems.list"
    params = {
        "apiKey": payload.api_key,
        "time": str(int(time())),
    }
    signature = create_signature(method_name, params, payload.api_secret)
    params["apiSig"] = signature
    url = URL(settings.POLYGON_HOST) / method_name

    try:
        async with ClientSession() as session:
            await get_response(session, url, params)
    except PolygonAPIError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Polygon credentials: {e}",
        )
    except Exception as e:
        logger.error(f"Polygon validation network error for user_id={user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to connect to Polygon API",
        )

    user.polygon_api_key = payload.api_key
    user.polygon_api_secret = payload.api_secret
    await db.commit()

    logger.info(f"Polygon API key linked: user_id={user_id}")
    return {"message": "Polygon account successfully linked"}
