from aiohttp import ClientSession

from logs.logs import log_middleware
from settings import YANDEX_CLIENT_ID, YANDEX_CLIENT_SECRET, REDIRECT_URI

@log_middleware
async def link():
    async with ClientSession() as client:
        async with client.get(f'https://oauth.yandex.ru/authorize?response_type=code&client_id={YANDEX_CLIENT_ID}&'
                                    f'redirect_uri={REDIRECT_URI}') as request_code:
            if request_code.status == 200:
                return request_code.url
            else:
                raise ConnectionError("Error while connecting to Yandex. Try again later.")


@log_middleware
async def token(verification_code):
    data = [
        ('grant_type', 'authorization_code'),
        ('client_id', YANDEX_CLIENT_ID),
        ('client_secret', YANDEX_CLIENT_SECRET),
        ('code', verification_code)
    ]

    async with ClientSession() as client:
        async with client.post('https://oauth.yandex.ru/token', data=data) as oauth_token:
            if oauth_token.status == 200:
                # save_credentials(OAuthToken.json()['access_token'], OAuthToken.json()['expires_in'])
                access_token = await oauth_token.json()
                return access_token['access_token']
            else:
                raise RuntimeError('Oops! Something went wrong. We are already working to fix it!')
