"""Test groups and points."""
from collections.abc import Iterable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import call, choice
from api.user.polygon.constants import FEEDBACK_POLICIES, POINTS_POLICIES


async def enable_groups(
    problem_id: int, testset: str, enable: bool, user_id: int, db: AsyncSession
) -> None:
    """``problem.enableGroups``."""
    await call(
        "problem.enableGroups", user_id, db, problemId=problem_id, testset=testset, enable=enable
    )


async def enable_points(problem_id: int, enable: bool, user_id: int, db: AsyncSession) -> None:
    """``problem.enablePoints``."""
    await call("problem.enablePoints", user_id, db, problemId=problem_id, enable=enable)


async def enable_treat_points_from_checker_as_percent(
    problem_id: int, enable: bool, user_id: int, db: AsyncSession
) -> None:
    """``problem.enableTreatPointsFromCheckerAsPercent`` (points must be enabled)."""
    await call(
        "problem.enableTreatPointsFromCheckerAsPercent", user_id, db,
        problemId=problem_id, enable=enable,
    )


async def view_test_group(
    problem_id: int,
    testset: str,
    user_id: int,
    db: AsyncSession,
    *,
    group: str | None = None,
) -> list[dict[str, Any]]:
    """``problem.viewTestGroup`` -> ``TestGroup[]`` (all groups or one)."""
    result = await call(
        "problem.viewTestGroup", user_id, db, problemId=problem_id, testset=testset, group=group
    )
    return result if isinstance(result, list) else []


async def save_test_group(
    problem_id: int,
    testset: str,
    group: str,
    user_id: int,
    db: AsyncSession,
    *,
    points_policy: str | None = None,
    feedback_policy: str | None = None,
    dependencies: Iterable[str] | str | None = None,
) -> None:
    """``problem.saveTestGroup``; fields left as ``None`` keep their value.

    A group's points are the points of its tests (``save_test(test_points=...)``);
    the method has no ``points`` parameter.
    """
    method = "problem.saveTestGroup"
    await call(
        method, user_id, db,
        problemId=problem_id,
        testset=testset,
        group=group,
        pointsPolicy=choice(points_policy, POINTS_POLICIES, "pointsPolicy", method=method),
        feedbackPolicy=choice(
            feedback_policy, FEEDBACK_POLICIES, "feedbackPolicy", method=method
        ),
        dependencies=(
            dependencies if dependencies is None or isinstance(dependencies, str)
            else [str(d) for d in dependencies]
        ),
    )
