"""Routes for problem statements, their rendering and resources."""

import mimetypes

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.polygon_task import SaveStatementRequest
from api.user.polygon.cache import refresh_statements
from api.user.polygon.methods import (get_statement_resources,
                                      render_statements, save_statement,
                                      save_statement_resource,
                                      view_statement_resource)
from app.database import get_db
from models.task.problem import PolygonProblem
from models.task.statement import PolygonStatement

router = APIRouter()


@router.get("/{polygon_id}/statement")
async def route_get_statements(
    polygon_id: int,
    refresh: bool = False,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return statements keyed by language from the cache; hit Polygon when
    nothing is cached or ``refresh=true``."""
    if not refresh:
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

    return await refresh_statements(polygon_id, user_id, db)


@router.patch("/{polygon_id}/statement")
async def route_save_statement(
    polygon_id: int,
    body: SaveStatementRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save a statement for the given language on Polygon and refresh the cache."""
    await save_statement(
        polygon_id,
        body.lang,
        user_id,
        db,
        encoding=body.encoding,
        name=body.name,
        legend=body.legend,
        input=body.input,
        output=body.output,
        scoring=body.scoring,
        interaction=body.interaction,
        notes=body.notes,
        tutorial=body.tutorial,
        show_in_review=body.show_in_review,
        show_cautions_and_grammatical_fixes=body.show_cautions_and_grammatical_fixes,
    )
    await refresh_statements(polygon_id, user_id, db)
    return {"ok": True}


@router.get("/{polygon_id}/statement/render")
async def route_render_statements(
    polygon_id: int,
    include_content: bool = False,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Rendered HTML/PDF statements and tutorials (``include_content`` adds base64 bodies)."""
    return await render_statements(polygon_id, user_id, db, include_content=include_content)


@router.get("/{polygon_id}/statement/resources")
async def route_get_statement_resources(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List statement resource files for the problem from Polygon."""
    return await get_statement_resources(polygon_id, user_id, db)


@router.get("/{polygon_id}/statement/resources/{name}")
async def route_view_statement_resource(
    polygon_id: int,
    name: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download one statement resource as-is (e.g. an image)."""
    content = await view_statement_resource(polygon_id, name, user_id, db)
    media_type = mimetypes.guess_type(name)[0] or "application/octet-stream"
    return Response(content=content, media_type=media_type)


@router.post("/{polygon_id}/statement/resources")
async def route_save_statement_resource(
    polygon_id: int,
    file: UploadFile = File(...),
    name: str | None = Form(default=None),
    check_existing: bool | None = Form(default=None),
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a statement resource (multipart ``file``; ``name`` defaults to its filename)."""
    await save_statement_resource(
        polygon_id,
        name or file.filename or "resource",
        await file.read(),
        user_id,
        db,
        check_existing=check_existing,
    )
    return {"ok": True}
