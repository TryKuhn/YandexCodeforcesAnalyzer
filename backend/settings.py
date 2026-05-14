from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    PROJECT_ROOT: Path = Path(__file__).parent.parent

    # General settings
    DEFAULT_PAGE_SIZE: int = 100

    # CORS settings
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

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

    # Polygon settings
    POLYGON_HOST: str = "https://polygon.codeforces.com/api"

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
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB,
        ).render_as_string(hide_password=False)


settings = Settings()  # type: ignore[call-arg]
