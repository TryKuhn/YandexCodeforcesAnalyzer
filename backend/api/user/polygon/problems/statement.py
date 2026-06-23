"""Routes for reading, saving, and listing resources of problem statements."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.polygon_task import SaveStatementRequest
from api.user.polygon.statement.get.resourse import get_statement_resources
from api.user.polygon.statement.get.setatement import get_statements
from api.user.polygon.statement.post.statement import save_statement
from app.database import get_db
from models.task.problem import PolygonProblem
from models.task.statement import PolygonStatement

router = APIRouter()


@router.get("/{polygon_id}/statement")
async def route_get_statements(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return cached statements keyed by language, falling back to Polygon when uncached."""
    problem_res = await db.execute(
        select(PolygonProblem).where(
            PolygonProblem.user_id == user_id,
            PolygonProblem.polygon_id == polygon_id,
        )
    )
    problem = problem_res.scalars().first()

    if problem:
        stmts_res = await db.execute(
            select(PolygonStatement).where(PolygonStatement.problem_id == problem.id)
        )
        cached = stmts_res.scalars().all()
        if cached:
            return {
                s.lang: {
                    "encoding": s.encoding,
                    "name": s.name or "",
                    "legend": s.legend or "",
                    "input": s.input or "",
                    "output": s.output or "",
                    "scoring": s.scoring,
                    "interaction": s.interaction,
                    "notes": s.notes,
                    "tutorial": s.tutorial,
                }
                for s in cached
            }

    return await get_statements(problem_id=polygon_id, user_id=user_id, db=db)


@router.patch("/{polygon_id}/statement")
async def route_save_statement(
    polygon_id: int,
    body: SaveStatementRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save a statement for the given language on Polygon."""
    await save_statement(
        problem_id=polygon_id,
        lang=body.lang,
        name=body.name,
        legend=body.legend,
        input_legend=body.input,
        output_legend=body.output,
        user_id=user_id,
        db=db,
        scoring=body.scoring,
        interaction=body.interaction,
        notes=body.notes,
        tutorial=body.tutorial,
        encoding=body.encoding,
    )
    return {"ok": True}


@router.get("/{polygon_id}/statement/resources")
async def route_get_statement_resources(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List statement resource files for the problem from Polygon."""
    return await get_statement_resources(problem_id=polygon_id, user_id=user_id, db=db)
