from datetime import datetime, timedelta, timezone
from typing import Tuple
from uuid import uuid4

from api.crypt import create_token
from settings import settings


def get_tokens(user_id: int, session_id: str) -> Tuple[str, str, datetime, datetime]:
    created_at = datetime.now(timezone.utc)
    expires_in = created_at + timedelta(minutes=settings.EXPIRES_REFRESH)

    data = {
        "user_id": user_id,
        "sid": session_id,
        "jti": str(uuid4()),
    }

    access_token = create_token(
        data=data, created_at=created_at, expires_delta=settings.EXPIRES_ACCESS
    )

    refresh_token = create_token(
        data=data, created_at=created_at, expires_delta=settings.EXPIRES_REFRESH
    )

    return (
        access_token,
        refresh_token,
        created_at.replace(tzinfo=None),
        expires_in.replace(tzinfo=None),
    )
