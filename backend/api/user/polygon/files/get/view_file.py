"""Read the content of a resource, source or aux file of a Polygon problem."""

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def view_file(
    problem_id: int,
    file_type: str,
    name: str,
    user_id: int,
    db: AsyncSession,
):
    """Returns resource/source/aux file content (problem.viewFile).

    file_type: 'resource' | 'aux' | 'source'
    """
    user = await get_user(user_id, db)
    result = await polygon_call(
        "problem.viewFile",
        {"problemId": str(problem_id), "type": file_type, "name": name},
        user,
    )
    return result.get("message", "") if isinstance(result, dict) else str(result)
