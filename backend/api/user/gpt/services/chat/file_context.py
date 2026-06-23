"""Lazily materialise a Polygon problem's files into the session.

Sessions opened from the Polygon tab have their files on Polygon, not in
``generated_files``. Before the chat executors read/modify files we pull the
problem's source files / solutions / script into the session once, so the modify
and answer executors operate on real content (and edits sync back via file_sync).
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm.attributes import flag_modified

from api.user.gpt.services.ai_file_helpers import (get_session_files,
                                                   upsert_ai_file)
from api.user.gpt.services.import_session import (_extract_statement,
                                                  _load_solutions,
                                                  _load_source_files)
from api.user.polygon.files.script.get.script import get_script
from api.user.polygon.statement.get.setatement import get_statements
from models.task.session import TaskSession

logger = logging.getLogger(__name__)


async def _ensure_statement(db: AsyncSession, session: TaskSession) -> None:
    """Lazy-load the statement from Polygon if the session has none yet."""
    if session.statement or not session.polygon_problem_id:
        return
    try:
        raw = await get_statements(session.polygon_problem_id, session.user_id, db)
        statement = _extract_statement(raw)
        if any(statement.values()):
            session.statement = statement
            flag_modified(session, "statement")
            await db.commit()
    except Exception as e:
        logger.warning(f"[{session.id}] statement lazy-load failed: {e}")


async def _load_all(db: AsyncSession, session: TaskSession) -> int:
    """Load source files + solutions + script from Polygon into the session
    (upsert overwrites existing rows). Returns the number of files loaded."""
    problem_id = session.polygon_problem_id
    if problem_id is None:
        return 0
    tech: dict = {}
    await _load_source_files(db, session.id, problem_id, session.user_id, tech)
    await _load_solutions(db, session, problem_id, session.user_id, tech)
    try:
        script = await get_script(problem_id, "tests", session.user_id, db)
        if script:
            await upsert_ai_file(db, session.id, "script", script, uploaded=True)
            tech["script"] = script
    except Exception:
        pass
    await db.commit()
    return len(tech)


async def ensure_files_loaded(db: AsyncSession, session: TaskSession) -> None:
    """Populate generated_files + statement from Polygon once (if empty)."""
    await _ensure_statement(db, session)

    if await get_session_files(db, session.id):
        return
    if not session.polygon_problem_id:
        return
    try:
        n = await _load_all(db, session)
        logger.info(f"[{session.id}] Lazy-loaded {n} files from Polygon")
    except Exception as e:
        logger.warning(f"[{session.id}] ensure_files_loaded failed: {e}")


async def reload_from_polygon(db: AsyncSession, session: TaskSession) -> dict:
    """Force-reload statement + all files from Polygon, overwriting the session.

    Used by the explicit "Синхронизировать с Polygon" button so the AI works
    against exactly what is on Polygon right now.
    """
    if not session.polygon_problem_id:
        return {"files": 0, "statement": False}

    statement_loaded = False
    try:
        raw = await get_statements(session.polygon_problem_id, session.user_id, db)
        statement = _extract_statement(raw)
        if any(statement.values()):
            session.statement = statement
            flag_modified(session, "statement")
            await db.commit()
            statement_loaded = True
    except Exception as e:
        logger.warning(f"[{session.id}] reload statement failed: {e}")

    files = 0
    try:
        files = await _load_all(db, session)
    except Exception as e:
        logger.warning(f"[{session.id}] reload files failed: {e}")

    logger.info(f"[{session.id}] Reloaded {files} files from Polygon")
    return {"files": files, "statement": statement_loaded}
