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
    user = await get_user(user_id, db)
    params: dict = {
        "problemId": str(problem_id),
        "name": name,
        "file": file_content,
    }
    if check_existing is not None:
        params["checkExisting"] = "true" if check_existing else "false"

    return await polygon_call("problem.saveStatementResource", params, user)
