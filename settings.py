from logging import basicConfig, INFO
from pathlib import Path

from os import environ
from dotenv import load_dotenv

ANALYZER_ROOT = Path(__file__).parent
DOTENV_PATH = ANALYZER_ROOT / '.env'

load_dotenv(dotenv_path=str(DOTENV_PATH))

basicConfig(filename='logs.txt',
            level=INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

DEFAULT_PAGE_SIZE = 100

YANDEX_HOST = environ['YANDEX_HOST']
YANDEX_CLIENT_ID = environ['YANDEX_CLIENT_ID']
YANDEX_CLIENT_SECRET = environ['YANDEX_CLIENT_SECRET']
YANDEX_TEST_OAUTH = environ['YANDEX_TEST_OAUTH']

CODEFORCES_HOST = environ['CODEFORCES_HOST']
CODEFORCES_TEST_KEY = environ['CODEFORCES_TEST_KEY']
CODEFORCES_TEST_SECRET = environ['CODEFORCES_TEST_SECRET']

DATABASE_NAME = environ['DATABASE_NAME']
DATABASE_USER = environ['DATABASE_USER']
DATABASE_PASSWORD = environ['DATABASE_PASSWORD']

REDIRECT_URI = environ['REDIRECT_URI']
