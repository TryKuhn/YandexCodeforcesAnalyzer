"""Application configuration loaded from environment / .env via pydantic-settings."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    """Typed application settings sourced from environment variables and .env."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    PROJECT_ROOT: Path = Path(__file__).parent.parent

    DEFAULT_PAGE_SIZE: int = 100

    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origins(self) -> list[str]:
        """Return CORS_ORIGINS parsed into a list of trimmed origin strings."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    ALGORITHM: str = "HS256"
    SECRET_KEY: str
    EXPIRES_ACCESS: int = 30
    EXPIRES_REFRESH: int = 43200

    YANDEX_HOST: str = "https://api.contest.yandex.net/api/public/v2"
    YANDEX_CLIENT_ID: str
    YANDEX_CLIENT_SECRET: str

    CODEFORCES_HOST: str = "https://codeforces.com/api"
    CF_CLIENT_ID: str
    CF_CLIENT_SECRET: str

    POLYGON_HOST: str = "https://polygon.codeforces.com/api"

    OPENAI_HOST: str = "https://openrouter.ai/api/v1"
    OPENAI_API_KEY: str

    # Hard cap on output tokens per LLM call. OpenRouter runs a pre-flight
    # affordability check on (prompt + max_tokens); with no cap it reserves the
    # model's full max output (e.g. 65536 for gpt-5.5-pro) and rejects the
    # request with 402 when the account balance can't cover that reservation.
    # Keep this comfortably below the balance headroom; raise it after topping
    # up OpenRouter credits if generations get truncated.
    LLM_MAX_TOKENS: int = 8000

    # OpenRouter provider routing (https://openrouter.ai/docs/provider-routing).
    # Some models are served only by a provider that geo-blocks the account's
    # region (e.g. gpt-5.5-pro via OpenAI-direct → HTTP 403 in a blocked region).
    # These let OpenRouter prefer/skip providers so such a model can route to an
    # allowed one. Comma-separated provider names; empty = OpenRouter's default.
    OPENROUTER_PROVIDER_ORDER: str = ""   # preferred first, e.g. "Azure,OpenAI"
    OPENROUTER_PROVIDER_IGNORE: str = ""  # skip these, e.g. "OpenAI"
    OPENROUTER_ALLOW_FALLBACKS: bool = True

    @property
    def openrouter_provider(self) -> dict:
        """Build the OpenRouter ``provider`` payload block from the settings.

        Returns ``{}`` when nothing is configured, so the payload stays clean.
        """
        order = [p.strip() for p in self.OPENROUTER_PROVIDER_ORDER.split(",") if p.strip()]
        ignore = [p.strip() for p in self.OPENROUTER_PROVIDER_IGNORE.split(",") if p.strip()]
        block: dict = {}
        if order:
            block["order"] = order
        if ignore:
            block["ignore"] = ignore
        if block:
            block["allow_fallbacks"] = self.OPENROUTER_ALLOW_FALLBACKS
        return block

    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432

    @property
    def database_url(self) -> str:
        """Build the asyncpg PostgreSQL connection URL from the POSTGRES_* settings."""
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB,
        ).render_as_string(hide_password=False)


settings = Settings()  # type: ignore[call-arg]
