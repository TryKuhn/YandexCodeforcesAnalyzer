"""``/api/ejudge``: export Polygon problems into ejudge contests."""
from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.user.ejudge import config as ejudge_config
from api.user.ejudge import export
from api.user.ejudge.common import EjudgeError
from api.user.polygon.client import PolygonAPIError
from app.database import get_db
from models.jobs.job import Job

ejudge_router = APIRouter()

# set at startup (like the judge queue); without it exports cannot be queued
_enqueue: Any = None


def set_enqueue(enqueue: Any) -> None:
    global _enqueue
    _enqueue = enqueue


class ExportIn(BaseModel):
    polygon_id: int
    contest_id: int = Field(gt=0, lt=1_000_000)
    package_id: int | None = None
    short_name: str | None = Field(default=None, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    problem_id: int | None = Field(default=None, gt=0)
    internal_name: str | None = Field(default=None, max_length=64, pattern=r"^[a-z0-9_-]+$")


def _http(e: Exception) -> HTTPException:
    if isinstance(e, PolygonAPIError):
        return HTTPException(status_code=e.http_status or 400, detail=f"Polygon: {e}")
    return HTTPException(status_code=400, detail=str(e))


async def _config(user_id: int, db: AsyncSession) -> ejudge_config.EjudgeConfig:
    try:
        return await ejudge_config.resolve(user_id, db)
    except EjudgeError as e:
        raise _http(e)


@ejudge_router.get("/status")
async def route_status(
    user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    """Whether the export is configured for this user (no secrets in the answer).

    ``source``: "user" -- the user's own ejudge (profile integration), "server" --
    the server-wide EJUDGE_* settings.
    """
    try:
        config = await ejudge_config.resolve(user_id, db)
    except EjudgeError as e:
        return {"configured": False, "source": "user", "error": str(e), "web_reload": False,
                "url": None, "ssh_host": None, "judges_dir": None}
    return {
        "configured": config.configured,
        "source": config.source,
        "web_reload": config.web_reload,
        "url": config.web_url or None,
        "ssh_host": config.ssh_host or None,
        "judges_dir": config.judges_dir,
    }


@ejudge_router.get("/contests/{contest_id}")
async def route_contest(
    contest_id: int, user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    """Score system and problems of a contest, read from its serve.cfg."""
    config = await _config(user_id, db)
    try:
        return await export.contest_info(contest_id, config=config)
    except EjudgeError as e:
        raise _http(e)


@ejudge_router.post("/preview")
async def route_preview(
    body: ExportIn,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """What the export would write (problem.cfg, valuer.cfg, the serve.cfg section)."""
    try:
        return await export.run_export(export.ExportRequest(**body.model_dump()), user_id, db, dry_run=True)
    except (EjudgeError, PolygonAPIError) as e:
        raise _http(e)


@ejudge_router.post("/export")
async def route_export(
    body: ExportIn,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Queue the export; poll ``/export/{job_id}``. The job resolves the user's ejudge itself."""
    config = await _config(user_id, db)
    if not config.configured:
        raise HTTPException(status_code=400, detail=export.NOT_CONFIGURED)
    if _enqueue is None:
        raise HTTPException(status_code=503, detail="очередь задач недоступна")
    try:
        export.require_allowed(config, body.contest_id)
    except EjudgeError as e:
        raise HTTPException(status_code=403, detail=str(e))
    job = await _enqueue(
        db, export.JOB_TYPE, {"request": body.model_dump(), "user_id": user_id}, user_id=user_id
    )
    return {"job_id": str(job.id)}


@ejudge_router.get("/export/{job_id}")
async def route_export_status(
    job_id: uuid.UUID,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    job = await db.get(Job, job_id)
    if job is None or job.user_id != user_id or job.type != export.JOB_TYPE:
        raise HTTPException(status_code=404, detail="Экспорт не найден")
    return {
        "job_id": str(job.id),
        "status": job.status,
        "progress": job.progress,
        "result": job.result,
        "error": job.error,
    }
