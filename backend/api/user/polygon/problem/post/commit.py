from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def commit_changes(
    problem_id: int,
    user_id: int,
    db: AsyncSession,
    minor_changes: bool = False,
    message: Optional[str] = None,
):
    """Commit working-copy changes via problem.commitChanges.

    Passes ``minorChanges``/``message`` when supplied and raises HTTP 409 if
    Polygon reports a commit conflict (``conflictOccurred``).
    """
    user = await get_user(user_id, db)
    params: dict = {"problemId": str(problem_id)}
    if minor_changes:
        params["minorChanges"] = "true"
    if message:
        params["message"] = message

    response = await polygon_call("problem.commitChanges", params, user)

    if isinstance(response, dict) and response.get("conflictOccurred"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conflict occurred while committing changes to the problem.",
        )
    return response
