"""Problem solutions."""
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import PolygonParamError, call, choice, one_of
from api.user.polygon.constants import EXTRA_SOLUTION_TAGS, SOLUTION_TAGS


async def get_solutions(
    problem_id: int, user_id: int, db: AsyncSession
) -> list[dict[str, Any]]:
    """``problem.solutions`` -> ``Solution[]``."""
    result = await call("problem.solutions", user_id, db, problemId=problem_id)
    return result if isinstance(result, list) else []


async def view_solution(problem_id: int, name: str, user_id: int, db: AsyncSession) -> str:
    """``problem.viewSolution`` -> solution source."""
    return await call(
        "problem.viewSolution", user_id, db, kind="text", problemId=problem_id, name=name
    )


async def save_solution(
    problem_id: int,
    name: str,
    file: bytes | str | None,
    user_id: int,
    db: AsyncSession,
    *,
    tag: str | None = None,
    source_type: str | None = None,
    check_existing: bool | None = None,
) -> None:
    """``problem.saveSolution`` (``file=None`` edits tag/type of an existing one)."""
    method = "problem.saveSolution"
    await call(
        method, user_id, db,
        problemId=problem_id,
        name=name,
        file=file,
        tag=choice(tag, SOLUTION_TAGS, "tag", method=method),
        sourceType=source_type,
        checkExisting=check_existing,
    )


async def edit_solution_extra_tags(
    problem_id: int,
    name: str,
    remove: bool,
    user_id: int,
    db: AsyncSession,
    *,
    testset: str | None = None,
    test_group: str | None = None,
    tag: str | None = None,
) -> None:
    """``problem.editSolutionExtraTags`` -- exactly one of ``testset``/``test_group``."""
    method = "problem.editSolutionExtraTags"
    one_of(method, testset=testset, testGroup=test_group)
    if not remove and tag is None:
        raise PolygonParamError("tag: обязателен при добавлении", method=method)
    await call(
        method, user_id, db,
        problemId=problem_id,
        name=name,
        remove=remove,
        testset=testset,
        testGroup=test_group,
        tag=None if remove else choice(tag, EXTRA_SOLUTION_TAGS, "tag", method=method),
    )
