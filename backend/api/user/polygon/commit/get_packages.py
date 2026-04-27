from time import time

from aiohttp import ClientSession
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yarl import URL

from api.user.polygon import create_signature, get_response
from models import User
from settings import settings


async def get_packages(problem_id: int, user_id: int, db: AsyncSession):
    method_name = 'problem.packages'

    user = await db.execute(select(User).filter_by(id=user_id))
    user = user.scalars().first()

    if not user.polygon_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Polygon API is not configured')

    current_time_unix = int(time())

    params = {
        'apiKey': user.polygon_api_key,
        'time': str(current_time_unix),
        'problemId': str(problem_id),
    }

    signature = create_signature(method_name, params, user.polygon_api_secret)
    params['apiSig'] = signature

    url = URL(settings.POLYGON_HOST) / method_name

    async with ClientSession() as session:
        return await get_response(session, url, params)
