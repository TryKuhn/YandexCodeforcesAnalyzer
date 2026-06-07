from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def set_generator(
    problem_id: int,
    name: str,
    file_content: str,
    user_id: int,
    db: AsyncSession,
    source_type: Optional[str] = None,
):
    """Upload a generator source file (problem.saveFile type=source)."""
    user = await get_user(user_id, db)
    params: dict = {
        "problemId": str(problem_id),
        "type": "source",
        "name": name,
        "file": file_content,
    }
    if source_type:
        params["sourceType"] = source_type
    return await polygon_call("problem.saveFile", params, user)
