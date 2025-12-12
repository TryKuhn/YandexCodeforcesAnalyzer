import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from dotenv import load_dotenv
from jose import jwt, JWTError

load_dotenv()

# Загружаем SECRET_KEY из .env
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def create_access_token(data: Dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """
    Создаёт JWT access token с заданными данными.

    Args:
        data: словарь данных для кодирования (например, {"sub": "user_id"})
        expires_delta: опциональная дельта времени жизни токена

    Returns:
        JWT token в виде строки
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Декодирует и проверяет JWT token.

    Args:
        token: JWT token строка

    Returns:
        Декодированный payload если токен валиден

    Raises:
        JWTError: если токен невалиден или просрочен
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise JWTError(f"Invalid or expired token: {str(e)}")

