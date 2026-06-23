"""Shared Polygon API client utilities.

Every service module imports `get_user` and `polygon_call` from here instead of
repeating the 40-line boilerplate in each file.
"""
from time import time

from aiohttp import ClientSession
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yarl import URL

from api.user.polygon.create_signature import create_signature
from api.user.polygon.get_response import PolygonAPIError, get_response
from models import User
from settings import settings


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

    Values in `params` should be strings or bytes. Bytes values (file content)
    are excluded from signature computation but included in the POST body.
    """
    text_params: dict[str, str] = {}
    binary_params: dict[str, bytes] = {}
    for k, v in params.items():
        if isinstance(v, bytes):
            binary_params[k] = v
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
    async with ClientSession() as client:
        return await get_response(client, url, request_data)


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
