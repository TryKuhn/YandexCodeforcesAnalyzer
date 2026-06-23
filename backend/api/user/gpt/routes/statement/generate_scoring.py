"""POST /generate-scoring — generate the Scoring LaTeX section."""
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy.orm.attributes import flag_modified

from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import GenerateScoringRequest
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.generation import scoring_gen, subtask_plan_gen
from api.user.gpt.services.sessions import get_session_or_404, now_utc
from app.database import get_db


@gpt_router.post("/generate-scoring")
async def generate_scoring(
    request: GenerateScoringRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate the Scoring LaTeX section for the session's statement.

    For output-only problems the scoring text is generated directly. Otherwise
    a subtask plan is generated and persisted on the session as the source of
    truth: it drives the scoring table, the per-group solutions and the Polygon
    group setup.
    """
    session = await get_session_or_404(db, request.session_id, user_id)
    if not session.statement:
        raise HTTPException(400, "Условие ещё не создано")

    from models.task.session import ProblemType

    settings = dict(session.problem_settings or {})
    enable_groups = settings.get("enable_groups", False)
    enable_points = settings.get("enable_points", False)
    is_output_only = session.problem_type == ProblemType.OUTPUT_ONLY
    if not enable_groups and not enable_points and not is_output_only:
        raise HTTPException(400, "Включите группы тестов или баллы в настройках задачи")

    if is_output_only:
        scoring_text = await scoring_gen.generate(
            session.statement, session.model, enable_groups, enable_points,
            problem_type=session.problem_type,
        )
    else:
        subtasks = await subtask_plan_gen.generate(session.statement, session.model)
        if not subtasks:
            raise HTTPException(500, "Не удалось спланировать подзадачи")
        settings["subtasks"] = subtasks
        settings["enable_groups"] = True
        settings["enable_points"] = True
        session.problem_settings = settings
        flag_modified(session, "problem_settings")
        scoring_text = subtask_plan_gen.render_scoring_latex(subtasks)

    stmt = dict(session.statement)
    stmt["scoring"] = scoring_text
    session.statement = stmt
    flag_modified(session, "statement")
    session.updated_at = now_utc()
    await db.commit()
    return {"session_id": session.id, "scoring": scoring_text}
