"""Push the AI statement (legend/input/output/scoring/interaction) to Polygon."""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.gpt.services.sync.file_sync import ensure_problem
from api.user.polygon.methods import commit_changes, save_statement
from models.task.session import ProblemType, TaskSession

logger = logging.getLogger(__name__)


async def sync_statement(
    db: AsyncSession,
    session: TaskSession,
    statement: dict,
    *,
    lang: str = "russian",
    polygon_commit: bool = True,
) -> int:
    """Save the statement to Polygon, auto-creating the problem if needed.

    The ``interaction`` section is only sent for interactive problems and the
    ``scoring`` section only when the statement carries one; sending empty
    strings is harmless but we keep the payload tidy.
    """
    problem_id = await ensure_problem(db, session)

    is_interactive = session.problem_type == ProblemType.INTERACTIVE
    interaction_text = statement.get("interaction", "") if is_interactive else ""

    await save_statement(
        problem_id=problem_id,
        lang=lang,
        user_id=session.user_id,
        db=db,
        encoding="utf-8",
        name=statement.get("name", ""),
        legend=statement.get("legend", ""),
        input=statement.get("input", ""),
        output=statement.get("output", ""),
        notes=statement.get("notes") or None,
        tutorial=statement.get("tutorial") or None,
        scoring=statement.get("scoring") or None,
        interaction=interaction_text or None,
    )

    if polygon_commit:
        await commit_changes(
            problem_id, session.user_id, db,
            minor_changes=True, message="ai-sync statement",
        )
    logger.info(f"[{session.id}] Synced statement to Polygon problem {problem_id}")
    return problem_id
