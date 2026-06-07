from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def save_script(
    problem_id: int, testset: str, source: str, user_id: int, db: AsyncSession
):
    user = await get_user(user_id, db)
    return await polygon_call(
        "problem.saveScript",
        {"problemId": str(problem_id), "testset": testset, "source": source},
        user,
    )
