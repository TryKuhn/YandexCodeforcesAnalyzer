from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas import LinkCodeforces
from api.user.codeforces import codeforces_router
from app.database import get_db
from models import User


@codeforces_router.post('/link')
async def link_codeforces(
        payload: LinkCodeforces,
        user_id: int = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    user = await db.execute(select(User).filter_by(id=user_id))
    user = user.scalars().first()

    # В будущем здесь можно добавить запрос к CF API для проверки валидности ключей
    user.codeforces_api_key = payload.api_key
    user.codeforces_api_secret = payload.api_secret

    await db.commit()

    return {'message': 'Codeforces account successfully linked'}

# def generate_pkce():
    # verifier = secrets.token_urlsafe(32)
    # challenge = base64.urlsafe_b64encode(
    #     hashlib.sha256(verifier.encode()).digest()
    # ).decode().rstrip("=")
    # return verifier, challenge
#
#
# class CodeforcesCallbackRequest(BaseModel):
#     code: str
#     code_verifier: str
#
#
# @codeforces_router.get('/auth_url')
# async def get_codeforces_auth_url():
#     verifier, challenge = generate_pkce()
#     state = secrets.token_urlsafe(16)
#
#     url = (
#         f'https://codeforces.com/oauth/authorize?'
#         f'response_type=code&'
#         f'client_id={settings.CF_CLIENT_ID}&'
#         f'redirect_uri={"http://localhost:5173/codeforces/callback"}&'
#         f'scope=openid&'
#         f'state={state}&'
#         f'code_challenge={challenge}&'
#         f'code_challenge_method=S256'
#     )
#     return {'url': url, 'code_verifier': verifier}
#
#
# @codeforces_router.post('/callback')
# async def codeforces_callback(
#         payload: CodeforcesCallbackRequest,
#         user_id: int = Depends(get_current_user),
#         db: AsyncSession = Depends(get_db)
# ):
#     async with httpx.AsyncClient() as client:
#         response = await client.post(
#             'https://codeforces.com/oauth/token',
#             data={
#                 'grant_type': 'authorization_code',
#                 'code': payload.code,
#                 'client_id': settings.CF_CLIENT_ID,
#                 'client_secret': settings.CF_CLIENT_SECRET,
#                 'redirect_uri': "http://localhost:5173/codeforces/callback",
#                 'code_verifier': payload.code_verifier,
#             }
#         )
#
#         if response.status_code != 200:
#             raise HTTPException(
#                 status_code=status.HTTP_400_BAD_REQUEST,
#                 detail='Failed to login with Codeforces API',
#             )
#
#         data = response.json()
#         token = data.get('access_token')
#
#         print(response.text)
#
#         user = await db.execute(select(User).filter_by(id=user_id))
#         user = user.scalars().first()
#
#         user.codeforces_access_token = token
#         await db.commit()
#
#         return {'message': 'Codeforces account successfully linked'}
