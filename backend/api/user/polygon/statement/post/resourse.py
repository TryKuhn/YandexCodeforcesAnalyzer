"""Save a statement resource file via the Polygon API."""
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def save_statement_resource(
    problem_id: int,
    name: str,
    file_content: bytes,
    user_id: int,
    db: AsyncSession,
    check_existing: Optional[bool] = None,
):
    """Upload a statement resource file via Polygon's
    ``problem.saveStatementResource``.

    ``check_existing`` maps to Polygon's ``checkExisting`` flag and is only
    sent when explicitly set (serialized as the strings ``"true"``/``"false"``)."""
    user = await get_user(user_id, db)
    params: dict = {
        "problemId": str(problem_id),
        "name": name,
        "file": file_content,
    }
    if check_existing is not None:
        params["checkExisting"] = "true" if check_existing else "false"

    return await polygon_call("problem.saveStatementResource", params, user)
