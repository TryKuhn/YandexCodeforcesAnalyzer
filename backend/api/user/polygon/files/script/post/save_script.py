"""Save the test-generation script of a Polygon problem testset."""

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def save_script(
    problem_id: int, testset: str, source: str, user_id: int, db: AsyncSession
):
    """Save the testset's script source (problem.saveScript)."""
    user = await get_user(user_id, db)
    return await polygon_call(
        "problem.saveScript",
        {"problemId": str(problem_id), "testset": testset, "source": source},
        user,
    )
