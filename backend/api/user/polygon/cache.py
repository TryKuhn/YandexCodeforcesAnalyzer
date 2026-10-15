"""Local cache of Polygon data: an API call + upsert into ``models.task`` tables.

The ``methods`` wrappers never touch the DB; these functions refresh the cache
(problem list, info, statements, solutions) and return the raw Polygon data.
"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon import methods
from models.task.problem import PolygonProblem
from models.task.solution import PolygonSolution
from models.task.statement import PolygonStatement


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _cached_problem(
    problem_id: int, user_id: int, db: AsyncSession
) -> PolygonProblem | None:
    result = await db.execute(
        select(PolygonProblem).filter_by(user_id=user_id, polygon_id=problem_id)
    )
    return result.scalars().first()


async def refresh_problem_list(
    user_id: int, db: AsyncSession, *, show_deleted: bool = False
) -> list[dict[str, Any]]:
    """``problems.list`` + upsert of the user's ``PolygonProblem`` rows."""
    problems = await methods.list_problems(user_id, db, show_deleted=show_deleted or None)
    items = [p for p in problems if p.get("id") is not None]

    existing = {
        p.polygon_id: p
        for p in (
            await db.execute(
                select(PolygonProblem).where(
                    PolygonProblem.user_id == user_id,
                    PolygonProblem.polygon_id.in_([p["id"] for p in items]),
                )
            )
        ).scalars()
    } if items else {}

    now = _utcnow()
    for item in items:
        fields = {
            "owner": item.get("owner", ""),
            "name": item.get("name", ""),
            "deleted": item.get("deleted", False),
            "favourite": item.get("favourite", False),
            "access_type": item.get("accessType"),
            "revision": item.get("revision"),
            "working_copy_revision": item.get("workingCopyRevision"),
            "latest_package": item.get("latestPackage"),
            "modified": item.get("modified", False),
            "list_fetched_at": now,
        }
        cached = existing.get(item["id"])
        if cached is None:
            db.add(PolygonProblem(user_id=user_id, polygon_id=item["id"], **fields))
        else:
            for key, value in fields.items():
                setattr(cached, key, value)

    await db.commit()
    return problems


async def refresh_problem_info(
    problem_id: int, user_id: int, db: AsyncSession
) -> dict[str, Any]:
    """``problem.info`` + update of the cached problem's limits/flags."""
    info = await methods.get_info(problem_id, user_id, db)
    if not isinstance(info, dict):
        return info

    cached = await _cached_problem(problem_id, user_id, db)
    if cached:
        cached.input_file = info.get("inputFile")
        cached.output_file = info.get("outputFile")
        cached.interactive = bool(info.get("interactive", False))
        cached.well_formed = bool(info.get("wellFormed", False))
        cached.time_limit = info.get("timeLimit")
        cached.memory_limit = info.get("memoryLimit")
        cached.info_fetched_at = _utcnow()
        await db.commit()
    return info


async def refresh_statements(
    problem_id: int, user_id: int, db: AsyncSession
) -> dict[str, dict[str, Any]]:
    """``problem.statements`` + upsert of ``PolygonStatement`` per language."""
    statements = await methods.get_statements(problem_id, user_id, db)
    cached = await _cached_problem(problem_id, user_id, db)
    if not statements or cached is None:
        return statements

    existing = {
        s.lang: s
        for s in (
            await db.execute(
                select(PolygonStatement).where(PolygonStatement.problem_id == cached.id)
            )
        ).scalars()
    }
    for lang, stmt in statements.items():
        fields = {
            "encoding": stmt.get("encoding", "utf-8"),
            "name": stmt.get("name", ""),
            "legend": stmt.get("legend", ""),
            "input": stmt.get("input", ""),
            "output": stmt.get("output", ""),
            "scoring": stmt.get("scoring"),
            "interaction": stmt.get("interaction"),
            "notes": stmt.get("notes"),
            "tutorial": stmt.get("tutorial"),
        }
        row = existing.get(lang)
        if row is None:
            db.add(PolygonStatement(problem_id=cached.id, lang=lang, **fields))
        else:
            for key, value in fields.items():
                setattr(row, key, value)
    await db.commit()
    return statements


async def refresh_solutions(
    problem_id: int, user_id: int, db: AsyncSession
) -> list[dict[str, Any]]:
    """``problem.solutions`` + upsert of ``PolygonSolution`` metadata.

    New rows are created with an empty ``content`` and ``uploaded=True``.
    """
    solutions = await methods.get_solutions(problem_id, user_id, db)
    cached = await _cached_problem(problem_id, user_id, db)
    if not solutions or cached is None:
        return solutions

    existing = {
        s.name: s
        for s in (
            await db.execute(
                select(PolygonSolution).where(PolygonSolution.problem_id == cached.id)
            )
        ).scalars()
    }
    for sol in solutions:
        name = sol.get("name", "")
        fields = {"source_type": sol.get("sourceType"), "tag": sol.get("tag")}
        row = existing.get(name)
        if row is None:
            db.add(PolygonSolution(
                problem_id=cached.id, name=name, content="", uploaded=True, **fields
            ))
        else:
            for key, value in fields.items():
                setattr(row, key, value)
    await db.commit()
    return solutions
