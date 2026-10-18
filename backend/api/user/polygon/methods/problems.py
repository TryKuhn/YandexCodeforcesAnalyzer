"""Global methods: problem list, problem creation, contest problems."""
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import PolygonAPIError, call


async def list_problems(
    user_id: int,
    db: AsyncSession,
    *,
    show_deleted: bool | None = None,
    problem_id: int | None = None,
    name: str | None = None,
    owner: str | None = None,
) -> list[dict[str, Any]]:
    """``problems.list`` -> ``Problem[]`` (filters are optional)."""
    result = await call(
        "problems.list", user_id, db,
        showDeleted=show_deleted, id=problem_id, name=name, owner=owner,
    )
    return result if isinstance(result, list) else []


async def create_problem(name: str, user_id: int, db: AsyncSession) -> int:
    """``problem.create`` -> id of the created problem."""
    result = await call("problem.create", user_id, db, name=name)
    problem_id = result.get("id") if isinstance(result, dict) else result
    if problem_id is None:
        raise PolygonAPIError(
            "Polygon не вернул id созданной задачи", http_status=502, method="problem.create"
        )
    return int(problem_id)


async def get_contest_problems(
    contest_id: int, user_id: int, db: AsyncSession
) -> dict[str, Any]:
    """``contest.problems`` -> ``{letter: Problem}``."""
    result = await call("contest.problems", user_id, db, contestId=contest_id)
    return result if isinstance(result, dict) else {}
