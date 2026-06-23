"""List the resource, source and aux files of a Polygon problem."""

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def get_files(problem_id: int, user_id: int, db: AsyncSession):
    """Returns {resourceFiles, sourceFiles, auxFiles} (problem.files)."""
    user = await get_user(user_id, db)
    return await polygon_call("problem.files", {"problemId": str(problem_id)}, user)
