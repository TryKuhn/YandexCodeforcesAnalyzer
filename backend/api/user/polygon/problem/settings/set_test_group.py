from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def set_test_group(
    problem_id: int,
    test_set: str,
    test_group: str,
    test_indices: str,
    user_id: int,
    db: AsyncSession,
):
    """test_indices: comma-separated list of test indices."""
    user = await get_user(user_id, db)
    return await polygon_call(
        "problem.setTestGroup",
        {
            "problemId": str(problem_id),
            "testset": test_set,
            "testGroup": test_group,
            "testIndices": test_indices,
        },
        user,
    )
