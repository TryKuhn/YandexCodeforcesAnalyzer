"""Push a single technical file to Polygon and keep the local DB row in sync.

``sync_file`` is the one entry point the chat/modify and build layers use to
write a file. It:
  1. upserts the ``TaskGeneratedFile`` row (uploaded=False),
  2. makes sure the problem exists on Polygon (auto-creates it if needed),
  3. routes to the correct Polygon setter via the file_registry ``category``,
  4. marks the row uploaded and commits the DB,
  5. optionally commits the Polygon working copy.

Routing is driven entirely by ``file_registry`` so a new file type is a
one-line registry change, not an edit here.
"""
import logging
import re
import time
from typing import Awaitable, Callable, Dict, Iterable

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.gpt.services.ai_file_helpers import (mark_uploaded,
                                                   resolve_filename,
                                                   upsert_ai_file)
from api.user.gpt.services.files.file_registry import get_spec
from api.user.polygon.files.checker.post.set_checker import set_checker
from api.user.polygon.files.generator.post.save_file import set_generator
from api.user.polygon.files.interactor.post.set_interactor import set_interactor
from api.user.polygon.files.script.post.save_script import save_script
from api.user.polygon.files.solution.post.save_solution import save_solution
from api.user.polygon.files.validator.post.set_validator import set_validator
from api.user.polygon.problem.post.commit import commit_changes
from api.user.polygon.problem.post.create import create_problem
from models.task.session import TaskSession

logger = logging.getLogger(__name__)


def _make_polygon_name(model: str, session_id: str) -> str:
    """Stable, Polygon-safe problem name derived from the model + session id."""
    model_short = re.sub(r"[^a-z0-9]", "", (model or "ai").split("/")[-1].lower())[:8]
    suffix = session_id[:4]
    timestamp = str(int(time.time()))[-5:]
    return f"{model_short}-task-{suffix}-{timestamp}"


async def ensure_problem(db: AsyncSession, session: TaskSession) -> int:
    """Return the Polygon problem id, creating the problem if it does not exist.

    Auto-creation lets an AI ``modify`` succeed even before the wizard has
    explicitly pushed the task to Polygon (plan default #2).
    """
    if session.polygon_problem_id:
        return session.polygon_problem_id

    name = _make_polygon_name(session.model, session.id)
    logger.info(f"[{session.id}] Auto-creating Polygon problem '{name}'")
    problem_id = await create_problem(name=name, user_id=session.user_id, db=db)
    session.polygon_problem_id = problem_id
    await db.commit()
    return problem_id


async def _push_to_polygon(
    category: str,
    problem_id: int,
    filename: str,
    content: str,
    tag: str | None,
    user_id: int,
    db: AsyncSession,
) -> None:
    """Dispatch to the Polygon setter that matches the registry category.

    The ``checker`` category covers both a regular checker and an output-only
    scorer; both go through ``set_checker``.
    """
    if category == "validator":
        await set_validator(problem_id, filename, content, user_id, db)
    elif category == "generator":
        await set_generator(problem_id, filename, content, user_id, db)
    elif category == "checker":
        await set_checker(problem_id, filename, content, user_id, db)
    elif category == "interactor":
        await set_interactor(problem_id, filename, content, user_id, db)
    elif category == "script":
        await save_script(problem_id, "tests", content, user_id, db)
    elif category == "solution":
        await save_solution(problem_id, filename, content, tag, user_id, db)
    else:
        raise ValueError(f"Unknown file category '{category}' for sync")


async def sync_file(
    db: AsyncSession,
    session: TaskSession,
    file_type: str,
    content: str,
    *,
    polygon_commit: bool = True,
) -> str:
    """Upsert a file locally and push it to Polygon. Returns the filename.

    Local upsert happens first so a Polygon failure still leaves the latest
    code in the DB. A file type without a registry spec (e.g. a custom solution
    ``sol_custom_*``) is treated as category=solution with its tag from
    ``solution_meta``.

    Set ``polygon_commit=False`` when syncing several files in a batch and
    committing the Polygon working copy once at the end (see ``sync_files``).
    """
    solution_meta = session.solution_meta or {}
    filename = resolve_filename(file_type, solution_meta)

    await upsert_ai_file(db, session.id, file_type, content, uploaded=False,
                         solution_meta=solution_meta)
    await db.commit()

    problem_id = await ensure_problem(db, session)
    spec = get_spec(file_type)
    if spec is not None:
        category, tag = spec.category, spec.tag
    else:
        category = "solution"
        tag = (solution_meta.get(file_type) or {}).get("tag", "OK")

    await _push_to_polygon(
        category, problem_id, filename, content, tag, session.user_id, db
    )

    await mark_uploaded(db, session.id, file_type)
    await db.commit()

    if polygon_commit:
        await commit_changes(
            problem_id, session.user_id, db,
            minor_changes=True, message=f"ai-sync {file_type}",
        )

    logger.info(f"[{session.id}] Synced {file_type} ({filename}) to Polygon")
    return filename


async def sync_files(
    db: AsyncSession,
    session: TaskSession,
    items: Iterable[tuple[str, str]],
) -> list[str]:
    """Sync a batch of (file_type, content) pairs, committing Polygon once.

    Used by the essence cascade and pack regeneration so a multi-file edit is a
    single Polygon commit instead of one per file.

    Resilient: a failure on one file is logged and skipped so the remaining
    files (e.g. all the solutions) still sync. Returns the file types that synced.
    """
    synced: list[str] = []
    for file_type, content in items:
        if not content:
            continue
        try:
            await sync_file(db, session, file_type, content, polygon_commit=False)
            synced.append(file_type)
        except Exception as e:
            logger.warning(f"[{session.id}] sync {file_type} failed, skipping: {e}")

    if synced and session.polygon_problem_id:
        try:
            await commit_changes(
                session.polygon_problem_id, session.user_id, db,
                minor_changes=True, message="ai-sync batch",
            )
        except Exception as e:
            logger.warning(f"[{session.id}] batch commit failed: {e}")
    return synced
