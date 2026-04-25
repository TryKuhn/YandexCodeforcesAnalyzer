from time import time

from aiohttp import ClientSession
from fastapi import Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yarl import URL

from api.crypt import get_current_user
from api.user.polygon import polygon_router, create_signature, get_response
from app.database import get_db
from models import User
from settings import settings


class BuildPackageResponse(BaseModel):
    detail: str


@polygon_router.post('/build_package',
                     summary='Собрать пакет для задачи',
                     description='Собирает полный пакет (windows + linux + standard) для задачи для выгрузки/импорта',
                     response_model=BuildPackageResponse,
                     response_description='Результат сборки пакета для задачи',
                     responses={
                            200: {
                                'description': 'Пакет успешно отправлен на сборку',
                                'content': {
                                    'application/json': {
                                        'example': {
                                            'detail': 'Пакет отправлен на сборку'
                                        }
                                    }
                                }
                            },
                     })
async def build_package(problem_id: int, user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    method_name = 'problem.buildPackage'

    user = await db.execute(select(User).filter_by(id=user_id))
    user = user.scalars().first()

    if not user.polygon_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Polygon API is not configured')

    current_time_unix = int(time())

    params = {
        'apiKey': user.polygon_api_key,
        'time': str(current_time_unix),
        'problemId': str(problem_id),
        'full': 'true',
        'verify': 'true',
    }

    signature = create_signature(method_name, params, user.polygon_api_secret)

    params['apiSig'] = signature

    url = URL(settings.POLYGON_HOST) / method_name

    async with ClientSession() as session:
        await get_response(session, url, params)

        return {'detail': 'Пакет отправлен на сборку'}
