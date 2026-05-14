import logging

import httpx
from fastapi import HTTPException
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from api.crypt import get_current_user
from api.user.yandex.base_yandex import router as yandex_router
from app.database import get_db
from models import User
from settings import settings

logger = logging.getLogger(__name__)


@yandex_router.get("/auth_url")
async def get_yandex_auth_url():
    url = (
        f"https://oauth.yandex.ru/authorize?response_type=code"
        f"&client_id={settings.YANDEX_CLIENT_ID}"
    )

    return {"url": url}


class YandexCallbackRequest(BaseModel):
    code: str


@yandex_router.post("/callback")
async def yandex_callback(
    payload: YandexCallbackRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth.yandex.ru/token",
                data={
                    "grant_type": "authorization_code",
                    "code": payload.code,
                    "client_id": settings.YANDEX_CLIENT_ID,
                    "client_secret": settings.YANDEX_CLIENT_SECRET,
                },
            )
    except httpx.RequestError as e:
        logger.error(f"Yandex OAuth network error for user_id={user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to connect to Yandex OAuth server",
        )

    if response.status_code != 200:
        logger.error(
            f"Yandex OAuth failed for user_id={user_id}: "
            f"status={response.status_code} body={response.text[:200]}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to login with Yandex API",
        )

    data = response.json()
    token = data.get("access_token")

    _r = await db.execute(select(User).filter_by(id=user_id))
    user = _r.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.yandex_access_token = token
    await db.commit()

    logger.info(f"Yandex account linked: user_id={user_id}")
    return {"message": "Yandex account successfully linked"}
