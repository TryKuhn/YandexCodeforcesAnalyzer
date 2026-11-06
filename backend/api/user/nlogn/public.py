"""``/api/public/v1``: the public API for other systems (the NlogN admin).

Authenticated ONLY by personal access tokens (``api.crypt.api_tokens``), never
by the jury JWT. Lets NlogN list the user's Polygon problems and publish one
into ejudge, then read the statement to save on its side (mode ``pull``).
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt.api_tokens import get_token_user
from api.user.nlogn import publish
from api.user.nlogn.router import check_ejudge, queue_publication
from api.user.polygon.client import PolygonAPIError
from api.user.polygon.problems.list import route_list_problems
from app.database import get_db
from models.jobs.job import Job, JobStatus
from models.user.integrations import NlognPublication
from models.user.user import User

public_router = APIRouter()


class PublicPublishIn(BaseModel):
    ejudge_contest_id: int = Field(gt=0, lt=1_000_000)
    short_name: str | None = Field(default=None, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    package_id: int | None = None


@public_router.get("/me")
async def public_me(user_id: int = Depends(get_token_user), db: AsyncSession = Depends(get_db)) -> dict:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="пользователь не найден")
    return {"id": user.id, "login": user.login}


@public_router.get("/problems")
async def public_problems(
    search: str = Query(default="", max_length=100),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    refresh: bool = True,
    user_id: int = Depends(get_token_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """The user's Polygon problems with the last ejudge binding of each."""
    try:
        listing = await route_list_problems(
            refresh=refresh, show_deleted=False, page=page, per_page=per_page, search=search,
            user_id=user_id, db=db,
        )
    except PolygonAPIError as e:
        raise HTTPException(status_code=502, detail=f"Polygon: {e}")
    ids = [item["polygon_id"] for item in listing["items"]]
    bindings: dict[int, dict] = {}
    if ids:
        rows = (await db.execute(
            select(NlognPublication)
            .where(NlognPublication.user_id == user_id, NlognPublication.polygon_id.in_(ids))
            .order_by(NlognPublication.updated_at.asc(), NlognPublication.id.asc())
        )).scalars().all()
        for row in rows:  # the latest one wins
            bindings[row.polygon_id] = {"contest_id": row.ejudge_contest_id, "problem_id": row.ejudge_problem_id,
                                        "short_name": row.short_name}
    items = [
        {
            "polygon_id": item["polygon_id"],
            "name": item["name"],
            "statement_name": item["statement_name"],
            "revision": item["revision"],
            "latest_package": item["latest_package"],
            "ejudge": bindings.get(item["polygon_id"]),
        }
        for item in listing["items"]
    ]
    return {"items": items, "total": listing["total"], "page": listing["page"], "per_page": listing["per_page"]}


@public_router.post("/problems/{polygon_id}/publish")
async def public_publish(
    polygon_id: int,
    body: PublicPublishIn,
    user_id: int = Depends(get_token_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Export the problem's latest READY (or the given) package into ejudge; the result has the statement."""
    await check_ejudge(user_id, db, body.ejudge_contest_id)
    request = publish.PublishRequest(
        polygon_id=polygon_id, ejudge_contest_id=body.ejudge_contest_id, short_name=body.short_name,
        package_id=body.package_id, mode="pull",
    )
    return {"job_id": await queue_publication(db, user_id, request)}


_RESULT_KEYS = ("ejudge_contest_id", "ejudge_problem_id", "short_name", "title", "html_statement",
                "text_statement", "time_limit_ms", "memory_limit_mb", "polygon_id", "package_id", "revision",
                "url", "warnings")


@public_router.get("/jobs/{job_id}")
async def public_job(
    job_id: uuid.UUID, user_id: int = Depends(get_token_user), db: AsyncSession = Depends(get_db)
) -> dict:
    job = await db.get(Job, job_id)
    if job is None or job.user_id != user_id or job.type != publish.JOB_TYPE:
        raise HTTPException(status_code=404, detail="задание не найдено")
    out: dict = {"job_id": str(job.id), "status": job.status, "progress": job.progress}
    result = job.result or {}
    if job.status == JobStatus.DONE.value:
        if result.get("ok") is False:
            # the handler reports expected failures as a result, not as a crash
            out["status"] = JobStatus.FAILED.value
            out["error"] = result.get("error") or "публикация не удалась"
        else:
            out["result"] = {k: result.get(k) for k in _RESULT_KEYS}
    elif job.status == JobStatus.FAILED.value:
        out["error"] = job.error or "публикация не удалась"
    return out
