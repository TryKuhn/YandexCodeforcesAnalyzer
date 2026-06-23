from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def enable_groups(
    problem_id: int, test_set: str, enable: bool, user_id: int, db: AsyncSession
):
    """Enable or disable test groups for a testset via problem.enableGroups."""
    user = await get_user(user_id, db)
    params = {
        "problemId": str(problem_id),
        "testset": test_set,
        "enable": "true" if enable else "false",
    }
    return await polygon_call("problem.enableGroups", params, user)
