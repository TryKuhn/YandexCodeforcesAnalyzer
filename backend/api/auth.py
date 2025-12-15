import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from dotenv import load_dotenv
from jose import JWTError, jwt

load_dotenv()

# Загружаем SECRET_KEY из .env
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY environment variable is not set. Please set it in your environment or .env file."
    )
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60


def create_access_token(
    data: Dict[str, Any], expires_delta: timedelta | None = None
) -> str:
    """
    Creates a JWT access token with the specified data.

    Args:
        data: A dictionary of data to encode (e.g., {"sub": "user_id"})
        expires_delta: Optional time delta for the token's lifetime

    Returns:
        JWT token as a string
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
    Decodes and verifies a JWT token.

    Args:
        token: JWT token string

    Returns:
        Decoded payload if the token is valid

    Raises:
        JWTError: if the token is invalid or expired
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError as e:
        raise JWTError(f"Invalid or expired token: {str(e)}")
