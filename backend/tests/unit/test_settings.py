"""Unit tests for settings.py — derived properties on the Settings model."""
from settings import Settings, settings


def test_cors_origins_splits_and_strips():
    s = Settings(
        CORS_ORIGINS="http://a.com, http://b.com ,, http://c.com",
        SECRET_KEY="x",
        YANDEX_CLIENT_ID="y",
        YANDEX_CLIENT_SECRET="y",
        CF_CLIENT_ID="c",
        CF_CLIENT_SECRET="c",
        OPENAI_API_KEY="o",
        POSTGRES_DB="d",
        POSTGRES_USER="u",
        POSTGRES_PASSWORD="p",
    )
    assert s.cors_origins == ["http://a.com", "http://b.com", "http://c.com"]


def test_database_url_renders_asyncpg_dsn():
    s = Settings(
        SECRET_KEY="x",
        YANDEX_CLIENT_ID="y",
        YANDEX_CLIENT_SECRET="y",
        CF_CLIENT_ID="c",
        CF_CLIENT_SECRET="c",
        OPENAI_API_KEY="o",
        POSTGRES_DB="mydb",
        POSTGRES_USER="myuser",
        POSTGRES_PASSWORD="mypass",
        POSTGRES_HOST="dbhost",
        POSTGRES_PORT=6543,
    )
    url = s.database_url
    assert url.startswith("postgresql+asyncpg://")
    assert "myuser" in url
    assert "mypass" in url  # password is rendered (hide_password=False)
    assert "dbhost" in url
    assert "6543" in url
    assert url.endswith("/mydb")


def test_singleton_settings_defaults():
    # Defaults defined on the model are applied to the imported singleton.
    assert settings.ALGORITHM == "HS256"
    assert settings.DEFAULT_PAGE_SIZE == 100
    assert settings.CODEFORCES_HOST == "https://codeforces.com/api"
    assert settings.POLYGON_HOST == "https://polygon.codeforces.com/api"
