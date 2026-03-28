from datetime import datetime, timezone, timedelta
from typing import Tuple

from api.crypt import create_token
from settings import EXPIRES_REFRESH, EXPIRES_ACCESS


def get_tokens(user_id: int) -> Tuple[str, str, datetime, datetime]:
    created_at = datetime.now(timezone.utc)
    expires_in = created_at + timedelta(minutes=EXPIRES_REFRESH)

    data = {
        'user_id': user_id,
    }

    access_token = create_token(
        data=data,
        created_at=created_at,
        expires_delta=EXPIRES_ACCESS
    )

    refresh_token = create_token(
        data=data,
        created_at=created_at,
        expires_delta=EXPIRES_REFRESH
    )

    return access_token, refresh_token, created_at, expires_in