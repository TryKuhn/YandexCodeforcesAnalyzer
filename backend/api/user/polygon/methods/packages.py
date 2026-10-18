"""Problem packages."""
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import call, choice
from api.user.polygon.constants import PACKAGE_TYPES


async def get_packages(problem_id: int, user_id: int, db: AsyncSession) -> list[dict[str, Any]]:
    """``problem.packages`` -> ``Package[]`` (order is not guaranteed)."""
    result = await call("problem.packages", user_id, db, problemId=problem_id)
    return result if isinstance(result, list) else []


async def download_package(
    problem_id: int,
    package_id: int,
    user_id: int,
    db: AsyncSession,
    *,
    package_type: str | None = None,
) -> bytes:
    """``problem.package`` -> zip archive (standard / linux / windows)."""
    method = "problem.package"
    return await call(
        method, user_id, db,
        kind="bytes",
        problemId=problem_id,
        packageId=package_id,
        type=choice(package_type, PACKAGE_TYPES, "type", method=method),
    )


async def build_package(
    problem_id: int,
    user_id: int,
    db: AsyncSession,
    *,
    full: bool | None = None,
    verify: bool | None = None,
) -> None:
    """``problem.buildPackage`` (``full``: also linux/windows; ``verify``: run solutions)."""
    await call("problem.buildPackage", user_id, db, problemId=problem_id, full=full, verify=verify)
