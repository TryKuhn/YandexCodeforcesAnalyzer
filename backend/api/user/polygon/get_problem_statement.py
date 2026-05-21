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


async def get_problem_statement(
    problem_id: int, user_id: int, db: AsyncSession
) -> dict:
    """Returns the first available statement for the given Polygon problem.

    Returns a dict with keys: name, legend, input, output, notes, tutorial.
    Prefers russian, falls back to english, then any language.
    """
    _r = await db.execute(select(User).filter_by(id=user_id))
    user = _r.scalars().first()

    if not user or not user.polygon_api_key or not user.polygon_api_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Polygon API is not configured",
        )

    method_name = "problem.statements"
    current_time_unix = int(time())

    params = {
        "apiKey": user.polygon_api_key,
        "time": str(current_time_unix),
        "problemId": str(problem_id),
    }
    signature = create_signature(method_name, params, user.polygon_api_secret)
    params["apiSig"] = signature

    url = URL(settings.POLYGON_HOST) / method_name

    async with ClientSession() as client:
        try:
            result = await get_response(client, url, params)
        except PolygonAPIError as e:
            raise HTTPException(status_code=400, detail=f"Polygon error: {e}")

    if not result:
        raise HTTPException(
            status_code=404, detail="No statement found for this problem"
        )

    statement = (
        result.get("russian")
        or result.get("english")
        or next(iter(result.values()), None)
    )

    if not statement:
        raise HTTPException(
            status_code=404, detail="No statement found for this problem"
        )

    return {
        "name": statement.get("name", ""),
        "legend": statement.get("legend", ""),
        "input": statement.get("input", ""),
        "output": statement.get("output", ""),
        "notes": statement.get("notes") or "",
        "tutorial": statement.get("tutorial") or "",
    }
