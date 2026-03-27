from datetime import datetime, timedelta
import jwt

from backend.settings import SECRET_KEY, ALGORITHM

def create_token(data: dict, created_at: datetime, expires_delta: int):
    to_encode = data.copy()

    expire = created_at + timedelta(minutes=expires_delta)
    to_encode.update({'exp': expire})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


def verify_token(token: str):
    try:
        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise RuntimeError('Token has expired.')
    except jwt.InvalidTokenError as e:
        raise RuntimeError(f'Invalid token. {e}')
