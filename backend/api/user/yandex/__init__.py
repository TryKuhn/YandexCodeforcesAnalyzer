"""Yandex.Contest integration: OAuth linking, standings, and submissions."""
from api.user.yandex.auth.login import get_yandex_auth_url, yandex_callback
from api.user.yandex.auth.logout import logout_yandex
from api.user.yandex.base_yandex import router as yandex_router
from api.user.yandex.standings.standings import yandex_standings
from api.user.yandex.submissions.submissions import yandex_submissions

__all__ = [
    "get_yandex_auth_url",
    "yandex_callback",
    "logout_yandex",
    "yandex_standings",
    "yandex_submissions",
    "yandex_router",
]
