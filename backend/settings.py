from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    PROJECT_ROOT: Path = Path(__file__).parent.parent

    # General settings
    DEFAULT_PAGE_SIZE: int = 100

    # JWT settings
    ALGORITHM: str = "HS256"
    SECRET_KEY: str
    EXPIRES_ACCESS: int = 30
    EXPIRES_REFRESH: int = 43200

    # Yandex OAuth2
    YANDEX_HOST: str = "https://api.contest.yandex.net/api/public/v2"
    YANDEX_CLIENT_ID: str
    YANDEX_CLIENT_SECRET: str

    # Codeforces settings
    CODEFORCES_HOST: str = "https://codeforces.com/api"
    CF_CLIENT_ID: str
    CF_CLIENT_SECRET: str
    CODEFORCES_TEST_KEY: str
    CODEFORCES_TEST_SECRET: str

    # Polygon settings
    POLYGON_HOST: str = 'https://polygon.codeforces.com/api'

    # OpenAI settings
    OPENAI_HOST: str = "https://openrouter.ai/api/v1"
    OPENAI_API_KEY: str

    # Database settings
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432

    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

settings = Settings()
