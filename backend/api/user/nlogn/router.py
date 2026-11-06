"""``/api/nlogn``: publishing problems to NlogN from the jury UI (job ``nlogn.publish``, mode push)."""
from __future__ import annotations

import uuid
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.user.ejudge import config as ejudge_config
from api.user.ejudge import export
from api.user.ejudge.common import EjudgeError
from api.user.integrations.nlogn import nlogn_status
from api.user.nlogn import publish
from app.database import get_db
from models.jobs.job import Job
from models.user.integrations import NlognAccount

nlogn_router = APIRouter()

# set at startup (like the ejudge export); without it publications cannot be queued
_enqueue: Any = None


def set_enqueue(enqueue: Any) -> None:
    global _enqueue
    _enqueue = enqueue


class PublishIn(BaseModel):
    polygon_id: int
    ejudge_contest_id: int = Field(gt=0, lt=1_000_000)
    short_name: str | None = Field(default=None, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    package_id: int | None = None
    title: str | None = Field(default=None, max_length=255)
    nlogn_contest_id: int | None = Field(default=None, gt=0)


async def check_ejudge(user_id: int, db: AsyncSession, contest_id: int) -> None:
    """HTTP errors for an export that cannot run (before queueing a job)."""
    try:
        config = await ejudge_config.resolve(user_id, db)
    except EjudgeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not config.configured:
        raise HTTPException(status_code=400, detail=export.NOT_CONFIGURED)
    try:
        export.require_allowed(config, contest_id)
    except EjudgeError as e:
        raise HTTPException(status_code=403, detail=str(e))


async def queue_publication(db: AsyncSession, user_id: int, request: publish.PublishRequest) -> str:
    if _enqueue is None:
        raise HTTPException(status_code=503, detail="очередь задач недоступна")
    job = await _enqueue(db, publish.JOB_TYPE, {"request": asdict(request), "user_id": user_id}, user_id=user_id)
    return str(job.id)


@nlogn_router.get("/status")
async def route_status(
    polygon_id: int | None = None,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """What the publication form needs: NlogN/ejudge links and the last publication of the problem."""
    nlogn = await nlogn_status(user_id=user_id, db=db)
    try:
        config = await ejudge_config.resolve(user_id, db)
        ejudge = {"configured": config.configured, "source": config.source, "ssh_host": config.ssh_host or None}
    except EjudgeError as e:
        ejudge = {"configured": False, "source": "user", "error": str(e), "ssh_host": None}
    last = None
    if polygon_id is not None:
        row = await publish.latest_publication(db, user_id, polygon_id)
        if row is not None:
            last = publish.publication_out(row, nlogn.get("base_url"))
    return {"nlogn": nlogn, "ejudge": ejudge, "publication": last}


@nlogn_router.post("/publish")
async def route_publish(
    body: PublishIn, user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    """Queue the publication (ejudge export + NlogN problem); poll ``/publish/{job_id}``."""
    if await db.get(NlognAccount, user_id) is None:
        raise HTTPException(status_code=400, detail="NlogN не привязан: подключите его в профиле")
    await check_ejudge(user_id, db, body.ejudge_contest_id)
    request = publish.PublishRequest(**body.model_dump(), mode="push")
    return {"job_id": await queue_publication(db, user_id, request)}


def job_out(job: Job) -> dict:
    return {"job_id": str(job.id), "status": job.status, "progress": job.progress,
            "result": job.result, "error": job.error}


@nlogn_router.get("/publish/{job_id}")
async def route_publish_status(
    job_id: uuid.UUID, user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    job = await db.get(Job, job_id)
    if job is None or job.user_id != user_id or job.type != publish.JOB_TYPE:
        raise HTTPException(status_code=404, detail="Публикация не найдена")
    return job_out(job)
