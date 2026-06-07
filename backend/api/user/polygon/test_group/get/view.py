from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def view_test_group(
    problem_id: int,
    testset: str,
    user_id: int,
    db: AsyncSession,
    group: Optional[str] = None,
):
    user = await get_user(user_id, db)
    params = {"problemId": str(problem_id), "testset": testset}
    if group:
        params["group"] = group
    return await polygon_call("problem.viewTestGroup", params, user)
