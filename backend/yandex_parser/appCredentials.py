from os import environ

from dotenv import load_dotenv

try:
    load_dotenv(dotenv_path='D:\\Projects\\PyCharm\\YandexCodeforcesAnalyzer\\.env')

    client_id = environ['client_id']
    client_secret = environ['client_secret']

    redirect_uri = environ['redirect_uri']

    yandex_host = environ['yandex_host']
except KeyError:
    raise RuntimeError('Oops! Something went wrong. We are already working to fix it!')
