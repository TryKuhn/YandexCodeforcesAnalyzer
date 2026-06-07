from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def edit_solution_extra_tags(
    problem_id: int,
    name: str,
    remove: bool,
    user_id: int,
    db: AsyncSession,
    testset: Optional[str] = None,
    test_group: Optional[str] = None,
    tag: Optional[str] = None,
):
    if (testset is None) == (test_group is None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exactly one of testset or testGroup must be specified",
        )
    user = await get_user(user_id, db)
    params: dict = {
        "problemId": str(problem_id),
        "name": name,
        "remove": "true" if remove else "false",
    }
    if testset:
        params["testset"] = testset
    if test_group:
        params["testGroup"] = test_group
    if not remove and tag:
        params["tag"] = tag
    return await polygon_call("problem.editSolutionExtraTags", params, user)
