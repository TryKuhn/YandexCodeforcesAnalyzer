from fastapi.params import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.user.yandex.base_yandex import router as yandex_router
from app.database import get_db
from models import User


@yandex_router.post("/logout")
async def logout_yandex(
    user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    user = await db.execute(select(User).filter_by(id=user_id))
    user = user.scalars().first()

    user.yandex_access_token = None
    await db.commit()

    return {"message": "Yandex account logged out"}
