"""Upload or update a solution for a Polygon problem."""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def save_solution(
    problem_id: int,
    name: str,
    file_content: str,
    tag: Optional[str],
    user_id: int,
    db: AsyncSession,
    source_type: Optional[str] = None,
    check_existing: Optional[bool] = None,
):
    """Upload / update a solution. `tag` is the 4th positional arg to match STEP_MAP."""
    user = await get_user(user_id, db)
    params: dict = {
        "problemId": str(problem_id),
        "name": name,
        "file": file_content,
    }
    if tag:
        params["tag"] = tag
    if source_type:
        params["sourceType"] = source_type
    if check_existing is not None:
        params["checkExisting"] = "true" if check_existing else "false"
    return await polygon_call("problem.saveSolution", params, user)
