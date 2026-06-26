"""Build the Polygon package and auto-repair build failures.

On READY → finalize (assign tests to groups, commit) and report success. On
FAILED → locate the offending file (error_parser) and give the AI up to 3
attempts to fix *that* file, rebuilding after each. If the file can't be
located, or 3 attempts are exhausted, escalate to the user with the raw error.
"""
import asyncio
import logging
from typing import Awaitable, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.gpt.services.ai_file_helpers import get_all_file_contents
from api.user.gpt.services.build import fix_gen
from api.user.gpt.services.build.error_parser import resolve_offending_file
from api.user.gpt.services.build.scoring_groups import assign_tests_to_groups
from api.user.gpt.services.files.file_registry import applicable_types
from api.user.gpt.services.sync.file_sync import sync_file
from api.user.polygon.problem.get.packages import get_packages
from api.user.polygon.problem.post.commit import commit_changes
from api.user.polygon.problem.post.package import build_package
from models.task.session import TaskSession

logger = logging.getLogger(__name__)

POLL_INTERVAL = 10
POLL_TIMEOUT = 600
MAX_FILE_FIX_ATTEMPTS = 3

_FIX_COMPANIONS: dict[str, list[str]] = {
    "generator": ["script"],
    "script": ["generator"],
}

StepCb = Callable[[str], Awaitable[None]]


async def _noop(_: str) -> None:
    """Default progress sink: ignore the step string."""
    return None


async def _poll(problem_id: int, user_id: int, db: AsyncSession,
                set_step: StepCb) -> tuple[str, str, Optional[int]]:
    """Poll problem.packages until READY/FAILED or timeout.

    Returns (state, comment, package_id). state ∈ READY|FAILED|TIMEOUT.
    """
    elapsed = 0
    while elapsed < POLL_TIMEOUT:
        await asyncio.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

        packages = await get_packages(problem_id, user_id, db)
        if not packages:
            continue
        latest = packages[-1]
        state = latest.get("state", "PENDING")
        await set_step(f"Сборка пакета: {state}...")

        if state == "READY":
            return "READY", "", latest.get("id")
        if state == "FAILED":
            return "FAILED", latest.get("comment", "Неизвестная ошибка сборки"), latest.get("id")

    return "TIMEOUT", "Таймаут ожидания сборки пакета", None


async def _build_once(problem_id: int, user_id: int, db: AsyncSession,
                      set_step: StepCb) -> tuple[str, str, Optional[int]]:
    """Commit pending changes, trigger one package build, and poll its result."""
    await commit_changes(problem_id, user_id, db, minor_changes=True, message="ai-build")
    await set_step("Запуск сборки пакета...")
    await build_package(problem_id=problem_id, user_id=user_id, db=db)
    return await _poll(problem_id, user_id, db, set_step)


async def _finalize(session: TaskSession, problem_id: int, db: AsyncSession,
                    scoring_groups: list[dict] | None, set_step: StepCb) -> dict:
    """Post-build: distribute tests across groups and re-commit.

    Returns {group: [test_indices]} so the caller can report it to the user.
    """
    if not scoring_groups:
        return {}
    await set_step("Назначение тестов группам...")
    mapping = await assign_tests_to_groups(
        session.id, problem_id, session.user_id, scoring_groups, db
    )
    try:
        await commit_changes(
            problem_id, session.user_id, db,
            minor_changes=True, message="ai-build groups",
        )
    except Exception as e:
        logger.warning(f"[{session.id}] re-commit after group assignment failed: {e}")
    return mapping


async def build_and_poll(
    db: AsyncSession,
    session: TaskSession,
    *,
    scoring_groups: list[dict] | None = None,
    set_step: StepCb = _noop,
) -> dict:
    """Build the package, repairing the offending file up to 3 times on failure.

    When the offender is ``generator`` or ``script``, its companion is passed to
    the fixer as read-only context: the two share named opt keys, so fixing one
    in isolation would leave them inconsistent (testlib 'unused key').

    Returns one of:
      {"status": "done", "package_id": int}
      {"status": "manual_fix", "offender": str|None, "error": str}
      {"status": "timeout", "error": str}
    """
    problem_id = session.polygon_problem_id
    if not problem_id:
        return {"status": "manual_fix", "offender": None,
                "error": "Polygon problem id is not set"}

    statement = session.statement or {}
    applicable = applicable_types(session.problem_type)

    state, comment, package_id = await _build_once(
        problem_id, session.user_id, db, set_step
    )
    if state == "READY":
        mapping = await _finalize(session, problem_id, db, scoring_groups, set_step)
        return {"status": "done", "package_id": package_id, "group_map": mapping}
    if state == "TIMEOUT":
        return {"status": "timeout", "error": comment}

    offender = await resolve_offending_file(comment, applicable)
    if not offender:
        logger.error(f"[{session.id}] Build failed, offender unknown: {comment}")
        return {"status": "manual_fix", "offender": None, "error": comment}

    # Each offending file gets up to MAX_FILE_FIX_ATTEMPTS tries of its OWN — the
    # count is PER FILE, not shared. When the build error moves to a different
    # file, that new file starts its own fresh counter. A total cap guards
    # against two files ping-ponging forever.
    attempts: dict[str, int] = {}
    prev_errors_by_file: dict[str, list[str]] = {}
    max_total = MAX_FILE_FIX_ATTEMPTS * 4

    while sum(attempts.values()) < max_total:
        attempts[offender] = attempts.get(offender, 0) + 1
        if attempts[offender] > MAX_FILE_FIX_ATTEMPTS:
            break  # this file exhausted its own attempts

        await set_step(
            f"Ошибка в {offender}, ИИ исправляет "
            f"(попытка {attempts[offender]}/{MAX_FILE_FIX_ATTEMPTS})..."
        )
        contents = await get_all_file_contents(db, session.id)
        code = contents.get(offender, "")
        related = {
            ft: contents[ft]
            for ft in _FIX_COMPANIONS.get(offender, [])
            if contents.get(ft)
        }
        prev_errors = prev_errors_by_file.setdefault(offender, [])
        try:
            fixed = await fix_gen.fix(
                offender, code, comment, statement, session.model,
                previous_errors=prev_errors or None,
                related_files=related or None,
            )
        except Exception as e:
            logger.warning(f"[{session.id}] fix_gen failed for {offender}: {e}")
            return {"status": "manual_fix", "offender": offender, "error": comment}

        await sync_file(db, session, offender, fixed)
        state, comment, package_id = await _build_once(
            problem_id, session.user_id, db, set_step
        )
        if state == "READY":
            await _finalize(session, problem_id, db, scoring_groups, set_step)
            return {"status": "done", "package_id": package_id}
        if state == "TIMEOUT":
            return {"status": "timeout", "error": comment}

        prev_errors.append(comment)
        next_offender = await resolve_offending_file(comment, applicable)
        if next_offender:
            offender = next_offender

    logger.error(
        f"[{session.id}] Build still failing after per-file fix attempts "
        f"(last offender {offender}): {comment}"
    )
    return {"status": "manual_fix", "offender": offender, "error": comment}
