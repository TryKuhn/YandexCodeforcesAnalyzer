from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def save_test_group(
    problem_id: int,
    test_set: str,
    group: str,
    points: int,
    user_id: int,
    db: AsyncSession,
    points_policy: Optional[str] = None,
    feedback_policy: Optional[str] = None,
    dependencies: Optional[list] = None,
):
    """Configure a test group's points and policies via problem.saveTestGroup.

    Optional points/feedback policies are sent only when provided; ``dependencies``
    is joined into the comma-separated form Polygon expects.
    """
    user = await get_user(user_id, db)
    params: dict = {
        "problemId": str(problem_id),
        "testset": test_set,
        "group": group,
        "points": str(points),
    }
    if points_policy:
        params["pointsPolicy"] = points_policy
    if feedback_policy:
        params["feedbackPolicy"] = feedback_policy
    if dependencies:
        params["dependencies"] = ",".join(str(d) for d in dependencies)

    return await polygon_call("problem.saveTestGroup", params, user)
