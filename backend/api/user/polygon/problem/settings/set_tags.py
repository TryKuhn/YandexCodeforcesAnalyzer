from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def set_tags(problem_id: int, tags: str, user_id: int, db: AsyncSession):
    """Save the problem's tags via problem.saveTags.

    ``tags`` is a comma-separated string of tag names.
    """
    user = await get_user(user_id, db)
    return await polygon_call(
        "problem.saveTags", {"problemId": str(problem_id), "tags": tags}, user
    )
