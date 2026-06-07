from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def get_script(problem_id: int, testset: str, user_id: int, db: AsyncSession):
    user = await get_user(user_id, db)
    result = await polygon_call(
        "problem.script",
        {"problemId": str(problem_id), "testset": testset},
        user,
    )
    return result.get("message", "") if isinstance(result, dict) else str(result)
