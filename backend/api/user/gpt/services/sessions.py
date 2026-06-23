"""Shared TaskSession helpers used across routes, chat, generation and build.

Centralises the small bits of bookkeeping that were previously duplicated as
private functions inside upload_orchestrator: fetching a session (404 on miss),
updating columns, appending to the chat log, and timestamps.
"""
import uuid
from datetime import datetime, timezone
from typing import Dict

from fastapi import HTTPException
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from models.task.session import ProblemType, TaskSession


def is_interactive(session: TaskSession) -> bool:
    """Single source of truth for the interactive branch: the problem type."""
    return session.problem_type == ProblemType.INTERACTIVE


def now_utc() -> datetime:
    """Naive UTC timestamp (DB columns are timezone-naive)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def now_iso() -> str:
    """ISO-8601 string of the current naive UTC time."""
    return now_utc().isoformat()


def new_id() -> str:
    """Generate a fresh random uuid4 string."""
    return str(uuid.uuid4())


async def get_session_or_404(
    db: AsyncSession, session_id: str, user_id: int | None = None
) -> TaskSession:
    """Load a session by id or raise 404. If ``user_id`` is given, enforce
    ownership (403 on mismatch)."""
    session = await db.get(TaskSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    if user_id is not None and session.user_id != user_id:
        raise HTTPException(status_code=403, detail="Нет доступа")
    return session


async def update_session(db: AsyncSession, session_id: str, data: Dict) -> None:
    """Patch session columns and commit. ``updated_at`` is refreshed."""
    data = {**data, "updated_at": now_utc()}
    await db.execute(
        update(TaskSession).where(TaskSession.id == session_id).values(**data)
    )
    await db.commit()


async def append_chat_log(db: AsyncSession, session_id: str, entries: list) -> None:
    """Append entries to chat_log and commit (survives a later crash)."""
    session = await db.get(TaskSession, session_id)
    if not session:
        return
    log = list(session.chat_log or [])
    log.extend(entries)
    session.chat_log = log
    flag_modified(session, "chat_log")
    session.updated_at = now_utc()
    await db.commit()


def chat_message(role: str, content: str, **extra) -> dict:
    """Build a chat_log entry with a stable id + timestamp."""
    return {
        "id": new_id(),
        "role": role,
        "content": content,
        "timestamp": now_iso(),
        **extra,
    }
