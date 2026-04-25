from time import time

from aiohttp import ClientSession
from fastapi import HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yarl import URL

from api.user.polygon import polygon_router, create_signature, get_response, add_source

from api.crypt import get_current_user
from app.database import get_db
from models import User
from settings import settings


@polygon_router.post('/set_checker')
async def set_checker(
        problem_id: int,
        name: str,
        checker_file: str,
        user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    method_name = 'problem.setChecker'

    user = await db.execute(select(User).filter_by(id=user_id))
    user = user.scalars().first()

    if not user.polygon_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Polygon API is not configured')

    await add_source(problem_id, name, checker_file, user_id, db)

    current_time_unix = int(time())

    params = {
        'apiKey': user.polygon_api_key,
        'time': str(current_time_unix),
        'problemId': str(problem_id),
        'checker': name,
    }

    signature = create_signature(method_name, params, user.polygon_api_secret)
    params['apiSig'] = signature

    url = URL(settings.POLYGON_HOST) / method_name

    async with ClientSession() as client:
        return await get_response(client, url, params)
