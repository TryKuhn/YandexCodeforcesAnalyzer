"""Problem working copy: update, discard, commit."""
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import PolygonAPIError, call


async def update_working_copy(problem_id: int, user_id: int, db: AsyncSession) -> None:
    """``problem.updateWorkingCopy``."""
    await call("problem.updateWorkingCopy", user_id, db, problemId=problem_id)


async def discard_working_copy(problem_id: int, user_id: int, db: AsyncSession) -> None:
    """``problem.discardWorkingCopy``."""
    await call("problem.discardWorkingCopy", user_id, db, problemId=problem_id)


async def commit_changes(
    problem_id: int,
    user_id: int,
    db: AsyncSession,
    *,
    minor_changes: bool | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    """``problem.commitChanges`` -> ``CommitResult``.

    Raises ``PolygonAPIError`` with HTTP 409 on ``conflictOccurred``.
    """
    method = "problem.commitChanges"
    result = await call(
        method, user_id, db,
        problemId=problem_id, minorChanges=minor_changes, message=message or None,
    )
    result = result if isinstance(result, dict) else {}
    if result.get("conflictOccurred"):
        raise PolygonAPIError(
            "Конфликт при коммите изменений задачи в Polygon",
            http_status=409,
            method=method,
            result=result,
        )
    return result
