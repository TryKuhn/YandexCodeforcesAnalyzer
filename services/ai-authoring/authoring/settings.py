"""Service configuration (environment / .env via pydantic-settings)."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    """Typed settings; the JWT secret and Postgres credentials are shared with the backend."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- auth (same values as the backend) -------------------------------------
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    # lifetime of the tokens this service mints to call the backend as a user
    SERVICE_TOKEN_MINUTES: int = 10

    # --- backend -------------------------------------------------------------
    BACKEND_API_URL: str = "http://backend:8000/api"
    BACKEND_TIMEOUT_SECONDS: float = 330.0

    # --- database ------------------------------------------------------------
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    # tests point this at sqlite; empty means "build from POSTGRES_*"
    DATABASE_URL: str = ""

    # --- LLM (OpenRouter) ----------------------------------------------------
    OPENAI_HOST: str = "https://openrouter.ai/api/v1"
    OPENAI_API_KEY: str
    LLM_MAX_TOKENS: int = 32000
    LLM_ROUTER_MAX_TOKENS: int = 2000
    LLM_TIMEOUT_SECONDS: float = 600.0
    OPENROUTER_PROVIDER_ORDER: str = ""
    OPENROUTER_PROVIDER_IGNORE: str = ""
    OPENROUTER_ALLOW_FALLBACKS: bool = True

    # --- sync / worker -------------------------------------------------------
    SYNC_INTERVAL_MINUTES: int = 5
    # only problems opened within this window are synced in the background
    SYNC_ACTIVE_WINDOW_HOURS: int = 24
    WORKER_POLL_SECONDS: float = 2.0
    # a running run whose heartbeat is older than this is considered abandoned
    RUN_STALE_SECONDS: int = 300
    BUILD_POLL_SECONDS: float = 10.0
    BUILD_TIMEOUT_SECONDS: int = 1800
    MAX_REPAIR_ATTEMPTS: int = 3

    @property
    def database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB,
        ).render_as_string(hide_password=False)

    @property
    def openrouter_provider(self) -> dict:
        """OpenRouter ``provider`` block, empty when nothing is configured."""
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


settings = Settings()  # type: ignore[call-arg]
