"""Routes for fetching and updating the AI task session attached to a problem."""

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from app.database import get_db
from models.task.session import PipelineStage, TaskSession

router = APIRouter()


DEFAULT_MODEL = "anthropic/claude-opus-4.8"


def default_problem_settings() -> dict:
    """Problem settings a fresh session starts with."""
    return {
        "input_file": "stdin",
        "output_file": "stdout",
        "interactive": False,
        "time_limit": 2000,
        "memory_limit": 256,
        "tags": [],
        "enable_groups": False,
        "enable_points": False,
    }


def new_task_session(
    user_id: int,
    polygon_id: int,
    *,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> TaskSession:
    """Build (not persist) a TaskSession for the problem with default settings."""
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    return TaskSession(
        id=str(uuid.uuid4()),
        user_id=user_id,
        model=model or DEFAULT_MODEL,
        system_prompt=system_prompt or "",
        history=[],
        stage=PipelineStage.STATEMENT,
        progress={"status": "idle"},
        statement=None,
        problem_settings=default_problem_settings(),
        polygon_problem_id=polygon_id,
        created_at=now,
        updated_at=now,
    )


class UpdateSessionRequest(BaseModel):
    """Request body for updating a session's model and/or system prompt."""

    model: Optional[str] = None
    system_prompt: Optional[str] = None


def _session_to_dict(session: TaskSession) -> dict:
    """Serialize a TaskSession into its API response dict."""
    return {
        "session_id": session.id,
        "model": session.model,
        "system_prompt": session.system_prompt,
        "problem_type": session.problem_type,
        "stage": session.stage,
        "progress": session.progress,
        "chat_log": session.chat_log,
        "problem_settings": session.problem_settings,
        "statement": session.statement,
        "solution_meta": session.solution_meta,
        "examples": session.examples,
    }


@router.get("/{polygon_id}/session")
async def route_get_session(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the problem's session, lazily creating one with defaults if absent."""
    result = await db.execute(
        select(TaskSession).where(
            TaskSession.polygon_problem_id == polygon_id,
            TaskSession.user_id == user_id,
        )
    )
    session = result.scalars().first()

    if session is None:
        session = new_task_session(user_id, polygon_id)
        db.add(session)
        await db.commit()
        await db.refresh(session)

    return _session_to_dict(session)


@router.patch("/{polygon_id}/session/settings")
async def route_update_session_settings(
    polygon_id: int,
    body: UpdateSessionRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update the session's model/system prompt, creating one with defaults if absent."""
    result = await db.execute(
        select(TaskSession).where(
            TaskSession.polygon_problem_id == polygon_id,
            TaskSession.user_id == user_id,
        )
    )
    session = result.scalars().first()

    if session is None:
        session = new_task_session(
            user_id, polygon_id, model=body.model, system_prompt=body.system_prompt
        )
        db.add(session)
    else:
        if body.model is not None:
            session.model = body.model
        if body.system_prompt is not None:
            session.system_prompt = body.system_prompt
        session.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    await db.commit()
    await db.refresh(session)
    return _session_to_dict(session)
