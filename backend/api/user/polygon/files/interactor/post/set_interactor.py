"""Upload and designate the interactor for a Polygon problem."""

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def set_interactor(
    problem_id: int, name: str, file_content: str, user_id: int, db: AsyncSession
):
    """Upload file as source then designate it as the interactor."""
    user = await get_user(user_id, db)
    await polygon_call(
        "problem.saveFile",
        {"problemId": str(problem_id), "type": "source", "name": name, "file": file_content},
        user,
    )
    return await polygon_call(
        "problem.setInteractor",
        {"problemId": str(problem_id), "interactor": name},
        user,
    )
