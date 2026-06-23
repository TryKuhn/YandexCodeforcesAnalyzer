"""PATCH /session/{session_id}/problem-type — switch regular/interactive/output-only.

``problem_type`` is the single source of truth for generation branching. We
mirror it into ``problem_settings`` for the settings sync (interactive flag),
force points on for output-only problems (they are always scored), and push the
interactive flag straight to Polygon so its problem checkbox tracks the type
(toggling away from interactive must clear it there too).
"""
import logging

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import UpdateProblemTypeRequest
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.sessions import get_session_or_404, now_utc
from api.user.polygon.problem.post.commit import commit_changes
from api.user.polygon.problem.settings.update_info import update_info
from app.database import get_db
from models.task.problem import PolygonProblem
from models.task.session import ProblemType

logger = logging.getLogger(__name__)


async def _push_interactive_to_polygon(
    db: AsyncSession, user_id: int, problem_id: int, interactive: bool
) -> None:
    """Set the Polygon problem's interactive flag and update the local cache row.

    Failures are logged but not raised: the session change has already been
    persisted, so a Polygon hiccup must not fail the request.
    """
    try:
        await update_info(
            problem_id=problem_id, user_id=user_id, db=db, interactive=interactive
        )
        await commit_changes(
            problem_id, user_id, db, minor_changes=True, message="ai-sync problem type",
        )
    except Exception as e:
        logger.warning(f"Failed to push interactive flag to Polygon {problem_id}: {e}")
        return

    cached = (
        await db.execute(
            select(PolygonProblem).where(
                PolygonProblem.user_id == user_id,
                PolygonProblem.polygon_id == problem_id,
            )
        )
    ).scalars().first()
    if cached is not None:
        cached.interactive = interactive
        await db.commit()


@gpt_router.patch("/session/{session_id}/problem-type")
async def update_problem_type(
    session_id: str,
    request: UpdateProblemTypeRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Switch the session's problem type, mirroring it into problem_settings.

    Sets the interactive flag from the type, forces points on for output-only
    problems (always scored), and pushes the interactive flag to Polygon when the
    problem already exists there.
    """
    session = await get_session_or_404(db, session_id, user_id)

    problem_type = ProblemType(request.problem_type)
    is_interactive = problem_type == ProblemType.INTERACTIVE
    session.problem_type = problem_type

    settings = dict(session.problem_settings or {})
    settings["interactive"] = is_interactive
    if problem_type == ProblemType.OUTPUT_ONLY:
        settings["enable_points"] = True
    session.problem_settings = settings
    flag_modified(session, "problem_settings")
    session.updated_at = now_utc()
    await db.commit()

    if session.polygon_problem_id:
        await _push_interactive_to_polygon(
            db, user_id, session.polygon_problem_id, is_interactive
        )

    return {
        "session_id": session_id,
        "problem_type": session.problem_type,
        "problem_settings": session.problem_settings,
    }
