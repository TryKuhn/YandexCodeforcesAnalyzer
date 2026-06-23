"""Resolve a ChatContext into the concrete target the executors act on.

- scope=statement → target is the statement JSON (cascade may touch files).
- scope=file      → target is exactly ``file_key`` (its own prompt).
- scope=task      → candidates are every file currently in the session; the
                    modify executor decides which to touch.
"""
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from api.pydantic_schemas.user.ai_task import ChatContext
from api.user.gpt.services.ai_file_helpers import get_session_files
from models.task.session import TaskSession


@dataclass
class ResolvedContext:
    """Concrete target for the executors.

    ``scope`` is one of task/statement/file; ``file_key`` is set only when
    scope == file; ``candidates`` lists the file types in play.
    """
    scope: str
    file_key: str | None = None
    candidates: list[str] = field(default_factory=list)


async def resolve(
    db: AsyncSession, session: TaskSession, context: ChatContext
) -> ResolvedContext:
    """Resolve a ChatContext into the concrete ResolvedContext target."""
    if context.scope == "statement":
        return ResolvedContext(scope="statement")

    if context.scope == "file":
        return ResolvedContext(
            scope="file",
            file_key=context.file_key,
            candidates=[context.file_key] if context.file_key else [],
        )

    files = await get_session_files(db, session.id)
    return ResolvedContext(scope="task", candidates=list(files.keys()))
