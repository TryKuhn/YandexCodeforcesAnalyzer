from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call_binary


async def download_package(
    problem_id: int,
    package_id: int,
    user_id: int,
    db: AsyncSession,
    package_type: Optional[str] = None,
) -> bytes:
    """Download a built package via problem.package and return its raw bytes.

    Optionally narrows to a specific package ``type`` when provided.
    """
    user = await get_user(user_id, db)
    params = {"problemId": str(problem_id), "packageId": str(package_id)}
    if package_type:
        params["type"] = package_type
    return await polygon_call_binary("problem.package", params, user)
