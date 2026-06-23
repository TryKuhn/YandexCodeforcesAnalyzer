"""User authentication: registration, login/logout, sessions, and tokens."""
from api.user.auth.base_auth import router as auth_router
from api.user.auth.change_password import change_password
from api.user.auth.location import get_location
from api.user.auth.login import login, register
from api.user.auth.logout import logout, logout_all
from api.user.auth.profile import get_me, get_sessions
from api.user.auth.refresh import refresh
from api.user.auth.tokens import get_tokens

__all__ = [
    "auth_router",
    "get_location",
    "get_tokens",
    "register",
    "login",
    "logout",
    "logout_all",
    "change_password",
    "get_me",
    "get_sessions",
    "refresh",
]
