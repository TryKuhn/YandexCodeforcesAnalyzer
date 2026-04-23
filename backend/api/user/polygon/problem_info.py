from time import time

from aiohttp import ClientSession
from sqlalchemy import select

from api.user.polygon import create_signature, get_response, polygon_router
from fastapi import Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from yarl import URL

from api.crypt import get_current_user
from app.database import get_db
from models import User
from settings import settings


@polygon_router.post('/problem_info')
async def problem_info(problem_id: int,
                       user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)
                       ):
    user = await db.execute(select(User).filter_by(id=user_id))
    user = user.scalars().first()

    if not user.polygon_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Polygon API is not configured')

    method_name = 'problem.info'

    current_time_unix = int(time())

    params = {
        'apiKey': user.polygon_api_key,
        'time': current_time_unix,
        'problemId': problem_id,
    }

    signature = create_signature(method_name, params, user.polygon_api_secret)
    params['apiSig'] = signature

    url = URL(settings.POLYGON_HOST) / method_name

    async with ClientSession() as session:
        return await get_response(session, url, params)
