"""Push problem settings (TL/ML/IO files/interactive) and tags to Polygon."""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.gpt.services.sync.file_sync import ensure_problem
from api.user.polygon.problem.post.commit import commit_changes
from api.user.polygon.problem.settings.set_tags import set_tags
from api.user.polygon.problem.settings.update_info import update_info
from models.task.session import ProblemType, TaskSession

logger = logging.getLogger(__name__)


async def sync_settings(
    db: AsyncSession,
    session: TaskSession,
    problem_settings: dict,
    *,
    polygon_commit: bool = True,
) -> int:
    """Push input/output filenames, limits and the interactive flag.

    The interactive flag is derived from ``problem_type`` (the single source of
    truth) rather than the legacy ``problem_settings['interactive']`` field.
    """
    problem_id = await ensure_problem(db, session)
    is_interactive = session.problem_type == ProblemType.INTERACTIVE

    await update_info(
        problem_id=problem_id,
        input_file_name=problem_settings.get("input_file", ""),
        output_file_name=problem_settings.get("output_file", ""),
        interactive=is_interactive,
        time_limit=problem_settings.get("time_limit", 0),
        memory_limit=problem_settings.get("memory_limit", 0),
        user_id=session.user_id,
        db=db,
    )

    if polygon_commit:
        await commit_changes(
            problem_id, session.user_id, db,
            minor_changes=True, message="ai-sync settings",
        )
    logger.info(f"[{session.id}] Synced settings to Polygon problem {problem_id}")
    return problem_id


async def sync_tags(
    db: AsyncSession,
    session: TaskSession,
    tags: list[str],
    *,
    polygon_commit: bool = True,
) -> int:
    """Push the problem tag list (comma-joined) to Polygon."""
    problem_id = await ensure_problem(db, session)
    if tags:
        await set_tags(problem_id, ",".join(tags), session.user_id, db)
        if polygon_commit:
            await commit_changes(
                problem_id, session.user_id, db,
                minor_changes=True, message="ai-sync tags",
            )
    return problem_id
