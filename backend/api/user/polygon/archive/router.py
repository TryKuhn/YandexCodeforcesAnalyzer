"""HTTP endpoints for importing an olympiad archive into Polygon."""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.user.gpt.services.llm.models import DEFAULT_MODEL
from api.user.polygon.archive.jobs import create_job, get_job
from api.user.polygon.archive.parser import polygon_prefix_from_archive
from api.user.polygon.archive.uploader import run_import
from api.user.polygon.client import get_user
from app.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

MAX_ARCHIVE_SIZE = 1024 * 1024 * 1024
"""Maximum accepted archive upload size (1 GB)."""

_background_tasks: set[asyncio.Task] = set()
"""Strong references to background import tasks.

Without holding a reference, a fire-and-forget ``asyncio.Task`` may be
garbage-collected mid-run; the done callback discards the entry on completion.
"""


@router.post("/archive/import")
async def route_import_archive(
    file: UploadFile,
    prefix: str | None = Form(None),
    generate_ai: bool = Form(True),
    ai_model: str = Form(DEFAULT_MODEL),
    build_package: bool = Form(True),
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Validate the upload and launch a background Polygon import job.

    Resolves the Polygon credentials up front (the background task has no DB
    access), checks the file is a non-empty ``.zip`` within the size cap, and
    derives the problem-name prefix from the request or the archive name.
    Returns the created job id and resolved prefix for the frontend to poll.
    """
    user = await get_user(user_id, db)

    filename = file.filename or "archive.zip"
    if not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Ожидается .zip архив")

    archive_bytes = await file.read()
    if len(archive_bytes) > MAX_ARCHIVE_SIZE:
        raise HTTPException(status_code=413, detail="Архив больше 1 ГБ")
    if not archive_bytes:
        raise HTTPException(status_code=400, detail="Пустой файл")

    stem = Path(filename).stem
    resolved_prefix = (prefix or "").strip() or polygon_prefix_from_archive(stem)
    if not resolved_prefix:
        raise HTTPException(
            status_code=400,
            detail="Не удалось определить префикс имён задач из имени архива — укажите его вручную",
        )

    job = create_job(user_id, archive_name=filename)
    job.prefix = resolved_prefix

    task = asyncio.create_task(
        run_import(
            job,
            archive_bytes,
            api_key=user.polygon_api_key or "",
            api_secret=user.polygon_api_secret or "",
            prefix=resolved_prefix,
            generate_ai=generate_ai,
            ai_model=ai_model,
            build_pkg=build_package,
        )
    )
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return {"job_id": job.id, "prefix": resolved_prefix}


@router.get("/archive/import/{job_id}")
async def route_import_status(
    job_id: str,
    user_id: int = Depends(get_current_user),
):
    """Return the current status of an import job owned by the caller."""
    job = get_job(job_id, user_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Импорт не найден")
    return job.to_dict()
