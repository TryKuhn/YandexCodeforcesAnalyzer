from time import time

from aiohttp import ClientSession
from fastapi import HTTPException, status, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yarl import URL

from api.crypt import get_current_user
from api.user.polygon import create_signature, get_response, polygon_router
from app.database import get_db
from models import User
from settings import settings


class CreateProblemResponse(BaseModel):
    problemId: int


@polygon_router.post('/create_problem',
                     summary='Создать новую задачу.',
                     description='Создать новую задачу. В ответе будет ID новой задачи, который нужно использовать для дальнейших действий с задачей.',
                     # response_model=CreateProblemResponse,
                     response_description='ID новой задачи.',
                     responses={
                         200: {
                             'description': 'Задача успешно создана.',
                             'content': {
                                 'application/json': {
                                     'example': {
                                         'problemId': 12345
                                     }
                                 }
                             }
                         },
                         403: {
                             'description': 'Ошибка при создании задачи.',
                             'content': {
                                 'application/json': {
                                     'example': {
                                         'detail': 'You already have such problem'
                                     }
                                 }
                             }
                         },
                     })
async def create_problem(name: str,
                         user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)
                         ):
    user = await db.execute(select(User).filter_by(id=user_id))
    user = user.scalars().first()

    if not user.polygon_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Polygon API is not configured')

    method_name = 'problem.create'

    current_time_unix = int(time())

    params = {
        'apiKey': user.polygon_api_key,
        'time': current_time_unix,
        'name': name,
    }

    signature = create_signature(method_name, params, user.polygon_api_secret)

    params['apiSig'] = signature

    url = URL(settings.POLYGON_HOST) / method_name

    async with ClientSession() as session:
        try:
            response = await get_response(session, url, params)

            # CHECK
            return response['id']
        except RuntimeError as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail=str(e))
