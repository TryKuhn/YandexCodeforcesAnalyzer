"""Read a problem's statement resources from the Polygon API."""
from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def get_statement_resources(problem_id: int, user_id: int, db: AsyncSession):
    """Fetch the list of statement resources for a problem via Polygon's
    ``problem.statementResources`` method."""
    user = await get_user(user_id, db)
    return await polygon_call(
        "problem.statementResources", {"problemId": str(problem_id)}, user
    )
