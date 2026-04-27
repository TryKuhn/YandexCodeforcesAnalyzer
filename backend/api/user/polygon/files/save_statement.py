from time import time
from typing import Optional

from aiohttp import ClientSession
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yarl import URL

from api.user.polygon.create_signature import create_signature
from api.user.polygon.get_response import get_response
from models import User
from settings import settings


async def save_statement(
    problem_id: int,
    lang: str,
    name: str,
    legend: str,
    input_legend: str,
    output_legend: str,
    scoring: Optional[str],
    interaction: Optional[str],
    notes: str | None,
    tutorial: str | None,
    user_id: int,
    db: AsyncSession,
):

    user = await db.execute(select(User).filter_by(id=user_id))
    user = user.scalars().first()

    if not user.polygon_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Polygon API is not configured",
        )

    method_name = "problem.saveStatement"

    current_time_unix = int(time())

    params = {
        "apiKey": user.polygon_api_key,
        "time": current_time_unix,
        "problemId": problem_id,
        "lang": lang,
        "encoding": "utf-8",
        "name": name,
        "legend": legend,
        "input": input_legend,
        "output": output_legend,
    }

    if scoring:
        params["scoring"] = scoring
    if interaction:
        params["interaction"] = interaction
    if notes:
        params["notes"] = notes
    if tutorial:
        params["tutorial"] = tutorial

    signature = create_signature(method_name, params, user.polygon_api_secret)
    params["apiSig"] = signature

    url = URL(settings.POLYGON_HOST) / method_name

    async with ClientSession() as session:
        return await get_response(session, url, params)
