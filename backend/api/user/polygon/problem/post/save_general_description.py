from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def save_general_description(
    problem_id: int, description: str, user_id: int, db: AsyncSession
):
    user = await get_user(user_id, db)
    return await polygon_call(
        "problem.saveGeneralDescription",
        {"problemId": str(problem_id), "description": description},
        user,
    )
