"""Link a user's Polygon API credentials after probing them for validity."""
import logging

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas import LinkCodeforces
from api.user.polygon.base_polygon import polygon_router
from api.user.polygon.client import PolygonAPIError, request
from app.database import get_db
from models import User

logger = logging.getLogger(__name__)


@polygon_router.post("/link")
async def link_polygon(
    payload: LinkCodeforces,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Validate and store the user's Polygon API credentials.

    Probes ``problems.list`` with the supplied key/secret before persisting
    them. Returns 400 if Polygon rejects the credentials and 502 if Polygon
    cannot be reached."""
    user = (await db.execute(select(User).filter_by(id=user_id))).scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        await request(
            "problems.list", {}, api_key=payload.api_key, api_secret=payload.api_secret
        )
    except PolygonAPIError as e:
        if e.http_status is not None and e.http_status >= 500:
            logger.error(f"Polygon validation failed for user_id={user_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Failed to connect to Polygon API",
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid Polygon credentials: {e}",
        )

    user.polygon_api_key = payload.api_key
    user.polygon_api_secret = payload.api_secret
    await db.commit()

    logger.info(f"Polygon API key linked: user_id={user_id}")
    return {"message": "Polygon account successfully linked"}
