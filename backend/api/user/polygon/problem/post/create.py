from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def create_problem(name: str, user_id: int, db: AsyncSession) -> int:
    """Creates a new problem on Polygon and returns its integer ID."""
    user = await get_user(user_id, db)
    result = await polygon_call("problem.create", {"name": name}, user)
    problem_id = result.get("id") if isinstance(result, dict) else result
    if problem_id is None:
        raise ValueError("Polygon did not return a problem id")
    return int(problem_id)
