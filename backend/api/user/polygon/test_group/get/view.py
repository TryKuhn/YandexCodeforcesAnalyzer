"""Read a single test group's settings from the Polygon API."""
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
    """Fetch test group info for a testset via Polygon's ``problem.viewTestGroup``.

    The optional ``group`` narrows the result to a single group; when omitted,
    all groups in the testset are returned."""
    user = await get_user(user_id, db)
    params = {"problemId": str(problem_id), "testset": testset}
    if group:
        params["group"] = group
    return await polygon_call("problem.viewTestGroup", params, user)
