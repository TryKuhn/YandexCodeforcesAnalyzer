from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.user.polygon.base_polygon import polygon_router
from app.database import get_db
from models import User


@polygon_router.post("/unlink")
async def unlink_polygon(
    user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    user = await db.execute(select(User).filter_by(id=user_id))
    user = user.scalars().first()

    user.polygon_api_key = None
    user.polygon_api_secret = None
    await db.commit()

    return {"message": "Polygon account successfully unlinked"}
