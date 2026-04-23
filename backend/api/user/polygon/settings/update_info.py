from time import time

from aiohttp import ClientSession
from fastapi import HTTPException, status
from fastapi.params import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yarl import URL

from api.crypt import get_current_user
from api.user.polygon import polygon_router, create_signature, get_response
from app.database import get_db
from models import User
from settings import settings


@polygon_router.post('/update_info')
async def update_info(
        problem_id: int,
        input_file_name: str,
        output_file_name: str,
        interactive: bool,
        time_limit: int,
        memory_limit: int,
        user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    method_name = 'problem.updateInfo'

    user = await db.execute(select(User).filter_by(id=user_id))
    user = user.scalars().first()

    if not user.polygon_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Polygon API is not configured')

    current_time_unix = int(time())

    params = {
        'apiKey': user.polygon_api_key,
        'time': current_time_unix,
        'problemId': problem_id,
    }

    if input_file_name:
        params['inputFile'] = input_file_name
    if output_file_name:
        params['outputFile'] = output_file_name
    if interactive:
        params['interactive'] = interactive
    if time_limit:
        params['timeLimit'] = time_limit
    if memory_limit:
        params['memoryLimit'] = memory_limit

    signature = create_signature(method_name, params, user.polygon_api_secret)
    params['apiSig'] = signature

    url = URL(settings.POLYGON_HOST) / method_name

    async with ClientSession() as session:
        return await get_response(session, url, params)
