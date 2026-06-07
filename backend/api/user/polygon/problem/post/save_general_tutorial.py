from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def save_general_tutorial(
    problem_id: int, tutorial: str, user_id: int, db: AsyncSession
):
    user = await get_user(user_id, db)
    return await polygon_call(
        "problem.saveGeneralTutorial",
        {"problemId": str(problem_id), "tutorial": tutorial},
        user,
    )
