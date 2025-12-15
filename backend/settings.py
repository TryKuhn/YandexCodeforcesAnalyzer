from os import environ
from pathlib import Path

from dotenv import load_dotenv

ANALYZER_ROOT = Path(__file__).parent.parent
DOTENV_PATH = ANALYZER_ROOT / ".env"

load_dotenv(dotenv_path=str(DOTENV_PATH))

# General settings
DEFAULT_PAGE_SIZE = 100

# Yandex OAuth2 settings
YANDEX_HOST = "https://api.contest.yandex.net/api/public/v2"
YANDEX_CLIENT_ID = environ["YANDEX_CLIENT_ID"]
YANDEX_CLIENT_SECRET = environ["YANDEX_CLIENT_SECRET"]
YANDEX_REDIRECT_URI = environ["YANDEX_REDIRECT_URI"]

# Codeforces OAuth2 settings
CODEFORCES_HOST = "https://codeforces.com/api"
CODEFORCES_TEST_KEY = environ["CODEFORCES_TEST_KEY"]
CODEFORCES_TEST_SECRET = environ["CODEFORCES_TEST_SECRET"]

# Database settings
POSTGRES_DB = environ["POSTGRES_DB"]
POSTGRES_USER = environ["POSTGRES_USER"]
POSTGRES_PASSWORD = environ["POSTGRES_PASSWORD"]
POSTGRES_URL = (
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@postgres:5432/{POSTGRES_DB}"
)
