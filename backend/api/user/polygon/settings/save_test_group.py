from time import time

from aiohttp import ClientSession
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yarl import URL

from api.user.polygon.create_signature import create_signature
from api.user.polygon.get_response import get_response
from models import User
from settings import settings


async def save_test_group(
    problem_id: int,
    test_set: str,
    group: str,
    points: int,
    points_policy: str,
    feedback_policy: str,
    dependencies: list[str],
    user_id: int,
    db: AsyncSession,
):
    """Configure a test group with points, dependencies, and feedback policy."""
    user_result = await db.execute(select(User).filter_by(id=user_id))
    user = user_result.scalars().first()

    if not user.polygon_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Polygon API is not configured",
        )

    method_name = "problem.saveTestGroup"
    current_time_unix = int(time())

    params = {
        "apiKey": user.polygon_api_key,
        "time": current_time_unix,
        "problemId": problem_id,
        "testset": test_set,
        "group": group,
        "points": points,
    }

    if points_policy:
        params["pointsPolicy"] = points_policy
    if feedback_policy:
        params["feedbackPolicy"] = feedback_policy
    if dependencies:
        params["dependencies"] = ",".join(str(d) for d in dependencies)

    signature = create_signature(method_name, params, user.polygon_api_secret)
    params["apiSig"] = signature

    url = URL(settings.POLYGON_HOST) / method_name

    async with ClientSession() as session:
        return await get_response(session, url, params)
