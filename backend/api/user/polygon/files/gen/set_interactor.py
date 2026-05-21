from time import time

from aiohttp import ClientSession
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yarl import URL

from api.user.polygon.create_signature import create_signature
from api.user.polygon.files.gen.add_source_file import add_source
from api.user.polygon.get_response import get_response
from models import User
from settings import settings


async def set_interactor(
    problem_id: int, name: str, interactor_file: str, user_id: int, db: AsyncSession
):
    method_name = "problem.setInteractor"

    user = await db.execute(select(User).filter_by(id=user_id))
    user = user.scalars().first()

    if not user.polygon_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Polygon API is not configured",
        )

    await add_source(problem_id, name, interactor_file, user_id, db)

    current_time_unix = int(time())

    params = {
        "apiKey": user.polygon_api_key,
        "time": str(current_time_unix),
        "problemId": str(problem_id),
        "interactor": name,
    }

    signature = create_signature(method_name, params, user.polygon_api_secret)
    params["apiSig"] = signature

    url = URL(settings.POLYGON_HOST) / method_name

    async with ClientSession() as client:
        return await get_response(client, url, params)
