from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def enable_points(problem_id: int, enable: bool, user_id: int, db: AsyncSession):
    user = await get_user(user_id, db)
    return await polygon_call(
        "problem.enablePoints",
        {"problemId": str(problem_id), "enable": "true" if enable else "false"},
        user,
    )
