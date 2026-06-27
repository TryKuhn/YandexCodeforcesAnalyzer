"""Shared Polygon API client utilities.

Every service module imports `get_user` and `polygon_call` from here instead of
repeating the 40-line boilerplate in each file.
"""
import asyncio
import logging
from time import time

from aiohttp import ClientError, ClientSession
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yarl import URL

from api.user.polygon.create_signature import create_signature
from api.user.polygon.get_response import PolygonAPIError, get_response
from models import User
from settings import settings

logger = logging.getLogger(__name__)

# Polygon's gateway (codeforces.com) intermittently returns 5xx HTML error pages,
# especially while a package is building. These are transient — retry a few times
# with backoff instead of failing the whole build.
_RETRY_STATUSES = {500, 502, 503, 504}
_MAX_RETRIES = 4


async def get_user(user_id: int, db: AsyncSession) -> User:
    """Fetch the user and ensure Polygon credentials are configured.

    Raises 401 if the user is missing or has no Polygon API key.
    """
    result = await db.execute(select(User).filter_by(id=user_id))
    user = result.scalars().first()
    if not user or not user.polygon_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Polygon API is not configured",
        )
    return user


async def polygon_call(method_name: str, params: dict, user: User):
    """Build auth params, sign, and POST to Polygon API. Returns parsed result.

    Polygon signs ALL request parameters, INCLUDING text content (source code,
    test input, statement text). So a value that is *text* must go into the
    signed ``text_params`` even when a caller passes it as ``bytes`` — otherwise
    Polygon rejects the request with 'apiKey: Incorrect signature'. Only genuine
    binary that is NOT valid UTF-8 (e.g. statement images) is excluded from the
    signature and sent as a raw multipart field.
    """
    text_params: dict[str, str] = {}
    binary_params: dict[str, bytes] = {}
    for k, v in params.items():
        if isinstance(v, bytes):
            try:
                text_params[k] = v.decode("utf-8")  # text → must be signed
            except UnicodeDecodeError:
                binary_params[k] = v                 # true binary → excluded
        else:
            text_params[k] = str(v)

    full_params: dict[str, str] = {
        "apiKey": user.polygon_api_key or "",
        "time": str(int(time())),
        **text_params,
    }

    sig = create_signature(method_name, full_params, user.polygon_api_secret or "")
    full_params["apiSig"] = sig

    request_data: dict = {**full_params, **binary_params}

    url = URL(settings.POLYGON_HOST) / method_name
    # The timestamp/signature stay valid for ±5 min, so reusing them across the
    # short backoff window is fine. Retry only TRANSIENT failures (gateway 5xx,
    # connection drops, timeouts) — logical Polygon errors (status≠OK / 4xx) are
    # deterministic and re-raised immediately.
    for attempt in range(_MAX_RETRIES):
        try:
            async with ClientSession() as client:
                return await get_response(client, url, request_data)
        except PolygonAPIError as e:
            transient = e.http_status in _RETRY_STATUSES
            if not transient or attempt == _MAX_RETRIES - 1:
                raise
            logger.warning(
                f"Polygon {method_name}: transient HTTP {e.http_status}, "
                f"retry {attempt + 1}/{_MAX_RETRIES - 1}"
            )
        except (ClientError, asyncio.TimeoutError) as e:
            if attempt == _MAX_RETRIES - 1:
                raise
            logger.warning(
                f"Polygon {method_name}: network error ({e!r}), "
                f"retry {attempt + 1}/{_MAX_RETRIES - 1}"
            )
        await asyncio.sleep(1.5 * (attempt + 1))


async def polygon_call_binary(method_name: str, params: dict, user: User) -> bytes:
    """Like polygon_call but returns raw bytes (for package zip downloads)."""
    full_params: dict[str, str] = {
        "apiKey": user.polygon_api_key or "",
        "time": str(int(time())),
        **{k: str(v) for k, v in params.items()},
    }
    sig = create_signature(method_name, full_params, user.polygon_api_secret or "")
    full_params["apiSig"] = sig

    url = URL(settings.POLYGON_HOST) / method_name
    async with ClientSession() as client:
        async with client.post(url, data=full_params) as response:
            if response.status != 200:
                text = await response.text()
                raise PolygonAPIError(
                    f"HTTP {response.status}: {text[:300]}",
                    http_status=response.status,
                    raw_response=text,
                )
            return await response.read()
