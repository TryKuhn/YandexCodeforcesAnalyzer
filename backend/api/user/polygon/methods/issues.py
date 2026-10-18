"""Problem cautions and issues."""
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import PolygonParamError, call, choice
from api.user.polygon.constants import ISSUE_TYPES, ISSUE_UPDATE_STATUSES

_MAX_ISSUE_TEXT = 16384


async def get_cautions(problem_id: int, user_id: int, db: AsyncSession) -> dict[str, Any]:
    """``problem.cautions`` -> ``ProblemCautions``."""
    result = await call("problem.cautions", user_id, db, problemId=problem_id)
    return result if isinstance(result, dict) else {}


async def get_issues(problem_id: int, user_id: int, db: AsyncSession) -> list[dict[str, Any]]:
    """``problem.issues`` -> ``Issue[]`` (most recently modified first)."""
    result = await call("problem.issues", user_id, db, problemId=problem_id)
    return result if isinstance(result, list) else []


async def add_issue(
    problem_id: int,
    issue_type: str,
    content: str,
    user_id: int,
    db: AsyncSession,
    *,
    assignee: str | None = None,
) -> dict[str, Any]:
    """``problem.addIssue`` -> the created ``Issue``."""
    method = "problem.addIssue"
    if not 1 <= len(content) <= _MAX_ISSUE_TEXT:
        raise PolygonParamError("content: от 1 до 16384 символов", method=method)
    return await call(
        method, user_id, db,
        problemId=problem_id,
        type=choice(issue_type, ISSUE_TYPES, "type", method=method),
        content=content,
        assignee=assignee,
    )


async def update_issue(
    problem_id: int,
    issue_id: int,
    user_id: int,
    db: AsyncSession,
    *,
    comment: str | None = None,
    status: str | None = None,
    issue_type: str | None = None,
    assignee: str | None = None,
) -> dict[str, Any]:
    """``problem.updateIssue`` -> the updated ``Issue``.

    ``assignee=""`` removes the assignee, ``None`` leaves it unchanged.
    """
    method = "problem.updateIssue"
    if comment is not None and len(comment) > _MAX_ISSUE_TEXT:
        raise PolygonParamError("comment: не длиннее 16384 символов", method=method)
    if not (comment and comment.strip()) and status is None and issue_type is None \
            and assignee is None:
        raise PolygonParamError("нужен непустой comment или хотя бы одно изменение", method=method)
    return await call(
        method, user_id, db,
        problemId=problem_id,
        issueId=issue_id,
        comment=comment,
        status=choice(status, ISSUE_UPDATE_STATUSES, "status", method=method),
        type=choice(issue_type, ISSUE_TYPES, "type", method=method),
        assignee=assignee,
    )
