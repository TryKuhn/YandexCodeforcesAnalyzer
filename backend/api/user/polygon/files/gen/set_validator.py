from time import time

from aiohttp import ClientSession
from fastapi import HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yarl import URL

from api.user.polygon.base_polygon import polygon_router
from api.user.polygon.files.gen.add_source_file import add_source
from api.user.polygon.create_signature import create_signature
from api.user.polygon.get_response import get_response

from api.crypt import get_current_user
from app.database import get_db
from models import User
from settings import settings


@polygon_router.post('/set_validator')
async def set_validator(
        problem_id: int,
        name: str,
        validator_file: str,
        user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):

    user = await db.execute(select(User).filter_by(id=user_id))
    user = user.scalars().first()

    if not user.polygon_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Polygon API is not configured')

    method_name = 'problem.setValidator'

    await add_source(problem_id, name, validator_file, user_id, db)

    current_time_unix = int(time())

    params = {
        'apiKey': user.polygon_api_key,
        'time': str(current_time_unix),
        'problemId': str(problem_id),
        'validator': name,
    }

    signature = create_signature(method_name, params, user.polygon_api_secret)
    params['apiSig'] = signature

    url = URL(settings.POLYGON_HOST) / method_name

    async with ClientSession() as client:
        return await get_response(client, url, params)
