from time import time

from aiohttp import ClientSession
from fastapi import Form, UploadFile, File, HTTPException, status, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yarl import URL

from api.crypt import get_current_user
from api.user.polygon import polygon_router, create_signature, get_response
from app.database import get_db
from models import User
from settings import settings


@polygon_router.post('/save_test')
async def save_test(
        problem_id: int,
        test_set: str,
        test_index: int,
        test_input: str,
        test_group: str,
        test_points: float,
        test_use_in_statements: bool,
        user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):

    user = await db.execute(select(User).filter_by(id=user_id))
    user = user.scalars().first()

    if not user.polygon_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Polygon API is not configured')

    method_name = 'problem.saveTest'

    current_time_unix = int(time())

    params = {
        'apiKey': user.polygon_api_key,
        'time': current_time_unix,
        'problemId': problem_id,
        'testset': test_set,
        'testIndex': test_index,
        'testInput': test_input,
    }

    if test_group:
        params['testGroup'] = test_group
    if test_points:
        params['testPoints'] = test_points

    if test_use_in_statements:
        params['testUseInStatements'] = 'true'

    signature = create_signature(method_name, params, user.polygon_api_secret)
    params['apiSig'] = signature

    url = URL(settings.POLYGON_HOST) / method_name

    async with ClientSession() as client:
        return await get_response(client, url, params)
