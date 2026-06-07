from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call
from models.task.problem import PolygonProblem
from models.task.statement import PolygonStatement


async def get_statements(problem_id: int, user_id: int, db: AsyncSession):
    """Returns map {lang -> Statement} and upserts into PolygonStatement table."""
    user = await get_user(user_id, db)
    result = await polygon_call(
        "problem.statements", {"problemId": str(problem_id)}, user
    )

    if isinstance(result, dict):
        cached_problem = (
            await db.execute(
                select(PolygonProblem).filter_by(user_id=user_id, polygon_id=problem_id)
            )
        ).scalars().first()

        if cached_problem:
            for lang, stmt in result.items():
                existing = (
                    await db.execute(
                        select(PolygonStatement).filter_by(
                            problem_id=cached_problem.id, lang=lang
                        )
                    )
                ).scalars().first()

                if existing:
                    existing.encoding = stmt.get("encoding", "utf-8")
                    existing.name = stmt.get("name", "")
                    existing.legend = stmt.get("legend", "")
                    existing.input = stmt.get("input", "")
                    existing.output = stmt.get("output", "")
                    existing.scoring = stmt.get("scoring")
                    existing.interaction = stmt.get("interaction")
                    existing.notes = stmt.get("notes")
                    existing.tutorial = stmt.get("tutorial")
                else:
                    db.add(PolygonStatement(
                        problem_id=cached_problem.id,
                        lang=lang,
                        encoding=stmt.get("encoding", "utf-8"),
                        name=stmt.get("name", ""),
                        legend=stmt.get("legend", ""),
                        input=stmt.get("input", ""),
                        output=stmt.get("output", ""),
                        scoring=stmt.get("scoring"),
                        interaction=stmt.get("interaction"),
                        notes=stmt.get("notes"),
                        tutorial=stmt.get("tutorial"),
                    ))
            await db.commit()

    return result
