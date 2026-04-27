from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas import LinkCodeforces
from api.user.polygon.base_polygon import polygon_router
from app.database import get_db
from models import User


@polygon_router.post("/link")
async def link_polygon(
    payload: LinkCodeforces,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user = await db.execute(select(User).filter_by(id=user_id))
    user = user.scalars().first()

    # В будущем здесь можно добавить запрос к Polygon API для проверки валидности ключей
    user.polygon_api_key = payload.api_key
    user.polygon_api_secret = payload.api_secret

    await db.commit()

    return {"message": "Polygon account successfully linked"}
