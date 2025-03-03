import requests
from yandex_parser.appCredentials import client_id, client_secret, redirect_uri


def link():
    request_code = requests.get(f'https://oauth.yandex.ru/authorize?response_type=code&client_id={client_id}&'
                                f'redirect_uri={redirect_uri}')

    if request_code.status_code == 200:
        return request_code.url
    else:
        # save_log(request_code.json()['error_description'], 'while getting auth link')
        raise ConnectionError("Error while connecting to Yandex. Try again later.")


def token(verification_code):
    data = [
        ('grant_type', 'authorization_code'),
        ('client_id', client_id),
        ('client_secret', client_secret),
        ('code', verification_code)
    ]

    OAuthToken = requests.post('https://oauth.yandex.ru/token', data=data)

    if OAuthToken.status_code == 200:
        # save_credentials(OAuthToken.json()['access_token'], OAuthToken.json()['expires_in'])
        return OAuthToken.json()['access_token']
    else:
        # save_log(OAuthToken.json()['error_description'], 'while authorization')
        raise RuntimeError('Oops! Something went wrong. We are already working to fix it!')
