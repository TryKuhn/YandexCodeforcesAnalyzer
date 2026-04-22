from api.user.auth.base_auth import router as auth_router

from api.user.auth.location import get_location
from api.user.auth.tokens import get_tokens

from api.user.auth.login import register, login
from api.user.auth.logout import logout, logout_all
from api.user.auth.change_password import change_password
from api.user.auth.profile import get_me, get_sessions
from api.user.auth.refresh import refresh

__all__ = [
    'auth_router',
    'get_location',
    'get_tokens',
]
