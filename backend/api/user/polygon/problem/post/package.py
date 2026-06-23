from time import time

from aiohttp import ClientSession
from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yarl import URL

from api.user.polygon.create_signature import create_signature
from api.user.polygon.get_response import get_response
from models import User
from settings import settings


class BuildPackageResponse(BaseModel):
    """Response payload for a package-build request."""

    detail: str


async def build_package(
        problem_id: int,
        user_id: int,
        db: AsyncSession
):
    """Trigger a full, verified package build via problem.buildPackage.

    Builds the request signature manually (rather than via the shared client)
    and sends ``full=true``/``verify=true``. Raises HTTP 401 when the user has no
    Polygon API key configured.
    """
    method_name = "problem.buildPackage"

    result = await db.execute(select(User).filter_by(id=user_id))
    user = result.scalars().first()

    if not user or not user.polygon_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Polygon API is not configured",
        )

    current_time_unix = int(time())

    params = {
        "apiKey": user.polygon_api_key,
        "time": str(current_time_unix),
        "problemId": str(problem_id),
        "full": "true",
        "verify": "true",
    }

    signature = create_signature(method_name, params, user.polygon_api_secret or "")

    params["apiSig"] = signature

    url = URL(settings.POLYGON_HOST) / method_name

    async with ClientSession() as session:
        await get_response(session, url, params)

        return {"detail": "Пакет отправлен на сборку"}
