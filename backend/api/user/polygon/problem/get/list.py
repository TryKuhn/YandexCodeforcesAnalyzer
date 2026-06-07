from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call
from models.task.problem import PolygonProblem


async def list_problems(
    user_id: int,
    db: AsyncSession,
    show_deleted: bool = False,
    problem_id: Optional[int] = None,
    name: Optional[str] = None,
    owner: Optional[str] = None,
):
    """Fetch problems list from Polygon and upsert into PolygonProblem cache."""
    user = await get_user(user_id, db)

    params: dict = {}
    if show_deleted:
        params["showDeleted"] = "true"
    if problem_id is not None:
        params["id"] = str(problem_id)
    if name:
        params["name"] = name
    if owner:
        params["owner"] = owner

    problems_data = await polygon_call("problems.list", params, user)
    if not isinstance(problems_data, list):
        problems_data = []

    now = datetime.utcnow()
    for item in problems_data:
        polygon_id = item.get("id")
        if polygon_id is None:
            continue

        cached = (
            await db.execute(
                select(PolygonProblem).filter_by(user_id=user_id, polygon_id=polygon_id)
            )
        ).scalars().first()

        if cached:
            cached.owner = item.get("owner", "")
            cached.name = item.get("name", "")
            cached.deleted = item.get("deleted", False)
            cached.favourite = item.get("favourite", False)
            cached.access_type = item.get("accessType")
            cached.revision = item.get("revision")
            cached.working_copy_revision = item.get("workingCopyRevision")
            cached.latest_package = item.get("latestPackage")
            cached.modified = item.get("modified", False)
            cached.list_fetched_at = now
        else:
            db.add(PolygonProblem(
                user_id=user_id,
                polygon_id=polygon_id,
                owner=item.get("owner", ""),
                name=item.get("name", ""),
                deleted=item.get("deleted", False),
                favourite=item.get("favourite", False),
                access_type=item.get("accessType"),
                revision=item.get("revision"),
                working_copy_revision=item.get("workingCopyRevision"),
                latest_package=item.get("latestPackage"),
                modified=item.get("modified", False),
                list_fetched_at=now,
            ))

    await db.commit()
    return problems_data
