"""POST /refine-statement — iterate the statement, regenerating files if needed."""
import json
import logging

from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import AIStatementResponse, RefineRequest
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.ai_file_helpers import upsert_all_ai_files
from api.user.gpt.services.generation import (file_gen, interaction_gen,
                                              scoring_gen, statement_gen)
from api.user.gpt.services.sessions import (get_session_or_404, is_interactive,
                                            now_utc)
from app.database import get_db
from models.task.session import PipelineStage

logger = logging.getLogger(__name__)


@gpt_router.post("/refine-statement", response_model=AIStatementResponse)
async def refine_statement(
    request: RefineRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Iterate the statement from user feedback, regenerating files if past review.

    Carries the interaction/scoring sections forward when present, and re-runs
    file generation when the session has already reached FILES_REVIEW.
    """
    session = await get_session_or_404(db, request.session_id, user_id)

    if session.stage not in (PipelineStage.STATEMENT, PipelineStage.FILES_REVIEW):
        raise HTTPException(400, f"Нельзя редактировать условие на этапе '{session.stage}'")

    if request.problem_settings:
        session.problem_settings = {
            **(session.problem_settings or {}), **request.problem_settings,
        }
        flag_modified(session, "problem_settings")

    problem_settings = request.problem_settings or session.problem_settings or {}

    history = list(session.history or [])
    if session.statement:
        history.append({"role": "assistant",
                        "content": json.dumps(session.statement, ensure_ascii=False)})
    history.append({"role": "user", "content": request.feedback})

    new_statement = await statement_gen.generate(
        user_idea=request.feedback,
        model=session.model,
        user_prompt=session.system_prompt,
        history=history,
    )
    stmt = dict(new_statement)

    if is_interactive(session):
        prev = (session.statement or {}).get("interaction")
        stmt["interaction"] = prev or await interaction_gen.generate(stmt, session.model)

    if problem_settings.get("enable_groups") or problem_settings.get("enable_points"):
        prev = (session.statement or {}).get("scoring")
        stmt["scoring"] = prev or await scoring_gen.generate(
            stmt, session.model,
            enable_groups=bool(problem_settings.get("enable_groups")),
            enable_points=bool(problem_settings.get("enable_points")),
            problem_type=session.problem_type,
        )

    session.history = history
    session.statement = stmt
    flag_modified(session, "statement")
    session.updated_at = now_utc()
    await db.commit()

    tech_data = None
    if session.stage == PipelineStage.FILES_REVIEW:
        try:
            tech_data, _skipped = await file_gen.generate_pack(
                session.problem_type, stmt, session.model
            )
            await upsert_all_ai_files(db, session.id, tech_data, uploaded=False)
            session.updated_at = now_utc()
            await db.commit()
        except Exception as e:
            logger.warning(f"Failed to regenerate files after statement refine: {e}")
            tech_data = None

    response = {"statement": stmt, "session_id": session.id, "stage": session.stage}
    if tech_data:
        response["technical_data"] = tech_data
    return response
