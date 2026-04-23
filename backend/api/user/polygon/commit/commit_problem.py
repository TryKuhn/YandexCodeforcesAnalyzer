from time import time

from aiohttp import ClientSession
from fastapi import status, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yarl import URL

from api.crypt import get_current_user
from api.user.polygon import polygon_router, create_signature, get_response
from app.database import get_db
from models import User
from settings import settings


class CommitResponse(BaseModel):
    detail: str


@polygon_router.post('/commit',
                     summary='Закоммитить изменения в задаче.',
                     description='Закоммитить изменения в задаче. Это нужно для того, чтобы изменения вступили в силу.'
                                 'Если не вызвать этот метод, то изменения не будут видны в тестирующей системе и при скачивании задачи.',
                     response_model=CommitResponse,
                     response_description='Результат коммита.',
                     responses={
                         200: {
                             'description': 'Успешный коммит.',
                             'content': {
                                 'application/json': {
                                     'example': {
                                         'message': 'Your changes have been committed',
                                     }
                                 }
                             }
                         },
                         403: {
                             'description': 'Пустой коммит',
                             'content': {
                                 'application/json': {
                                     'example': {
                                         'detail': 'No changes'
                                     }
                                 }
                             }
                         },
                         409: {
                             'description': 'Конфликт при коммите',
                             'content': {
                                 'application/json': {
                                     'example': {
                                         'detail': 'Conflict occurred while committing changes to the problem.'
                                     }
                                 }
                             }
                         },
                     })
async def commit(problem_id: int, user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    method_name = 'problem.commitChanges'

    user = await db.execute(select(User).filter_by(id=user_id))
    user = user.scalars().first()

    if not user.polygon_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Polygon API is not configured')

    current_time_unix = int(time())

    params = {
        'apiKey': user.polygon_api_key,
        'time': str(current_time_unix),
        'problemId': str(problem_id),
        'minorChanges': 'true',
        'message': 'gpt-generated-task',
    }

    signature = create_signature(method_name, params, user.polygon_api_secret)

    params['apiSig'] = signature

    url = URL(settings.POLYGON_HOST) / method_name

    async with ClientSession() as session:
        response = await get_response(session, url, params)
        if response['conflictOccurred']:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Conflict occurred while committing changes to the problem.'
            )
        if not response['committed']:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=response['message']
            )

        return {'detail': response['message']}
