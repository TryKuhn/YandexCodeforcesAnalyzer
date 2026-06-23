"""Routes for listing cached problems with pagination, search, and statement names."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.user.polygon.problem.get.list import list_problems
from app.database import get_db
from models.task.problem import PolygonProblem
from models.task.statement import PolygonStatement

router = APIRouter()

PER_PAGE_DEFAULT = 20
PER_PAGE_MAX = 100


def _serialize(p: PolygonProblem, statement_name: str | None) -> dict:
    """Serialize a cached PolygonProblem into the list-item response dict."""
    return {
        "polygon_id": p.polygon_id,
        "name": p.name,
        "statement_name": statement_name,
        "owner": p.owner,
        "deleted": p.deleted,
        "favourite": p.favourite,
        "access_type": p.access_type,
        "revision": p.revision,
        "working_copy_revision": p.working_copy_revision,
        "latest_package": p.latest_package,
        "modified": p.modified,
        "list_fetched_at": p.list_fetched_at.isoformat() if p.list_fetched_at else None,
        "info_fetched_at": p.info_fetched_at.isoformat() if p.info_fetched_at else None,
    }


async def _get_statement_names(
    db: AsyncSession, problem_db_ids: list[int]
) -> dict[int, str]:
    """Returns {problem_db_id: statement_name}, preferring Russian over other languages."""
    if not problem_db_ids:
        return {}
    rows = await db.execute(
        select(PolygonStatement.problem_id, PolygonStatement.lang, PolygonStatement.name)
        .where(PolygonStatement.problem_id.in_(problem_db_ids))
        .where(PolygonStatement.name.isnot(None))
        .where(PolygonStatement.name != "")
    )
    stmt_map: dict[int, str] = {}
    for problem_id, lang, name in rows:
        if problem_id not in stmt_map or lang == "russian":
            stmt_map[problem_id] = name
    return stmt_map


@router.get("/")
async def route_list_problems(
    refresh: bool = True,
    show_deleted: bool = False,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=PER_PAGE_DEFAULT, ge=1, le=PER_PAGE_MAX),
    search: str = Query(default=""),
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List problems with pagination and optional name search.

    When refresh=True (default), hits Polygon first and updates the cache.
    Returns paginated results with statement_name populated from the cached
    PolygonStatement table (preferring the Russian statement name).
    search filters by technical name or statement name (case-insensitive).
    """
    if refresh:
        await list_problems(user_id=user_id, db=db, show_deleted=show_deleted)

    base_filter = [PolygonProblem.user_id == user_id]
    if not show_deleted:
        base_filter.append(PolygonProblem.deleted.is_(False))

    if search.strip():
        term = f"%{search.strip().lower()}%"
        stmt_subq = (
            select(PolygonStatement.problem_id)
            .where(func.lower(PolygonStatement.name).like(term))
            .scalar_subquery()
        )
        base_filter.append(
            or_(
                func.lower(PolygonProblem.name).like(term),
                PolygonProblem.id.in_(stmt_subq),
            )
        )

    total: int = (
        await db.execute(
            select(func.count()).select_from(
                select(PolygonProblem).where(*base_filter).subquery()
            )
        )
    ).scalar_one()

    rows = (
        await db.execute(
            select(PolygonProblem)
            .where(*base_filter)
            .order_by(PolygonProblem.polygon_id.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
        )
    ).scalars().all()

    stmt_map = await _get_statement_names(db, [p.id for p in rows])

    return {
        "items": [_serialize(p, stmt_map.get(p.id)) for p in rows],
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total + per_page - 1) // per_page),
        "search": search,
    }
