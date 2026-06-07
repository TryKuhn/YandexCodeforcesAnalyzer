from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def get_tests(
    problem_id: int,
    testset: str,
    user_id: int,
    db: AsyncSession,
    no_inputs: Optional[bool] = None,
):
    user = await get_user(user_id, db)
    params = {"problemId": str(problem_id), "testset": testset}
    if no_inputs:
        params["noInputs"] = "true"
    return await polygon_call("problem.tests", params, user)
