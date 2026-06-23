"""POST /approve-statement — lock the statement and generate the file pack."""
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import ApproveStatementRequest
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.ai_file_helpers import upsert_all_ai_files
from api.user.gpt.services.generation import (file_gen, interaction_gen,
                                              scoring_gen)
from api.user.gpt.services.sessions import (get_session_or_404, is_interactive,
                                            now_utc)
from app.database import get_db
from models.task.session import PipelineStage


@gpt_router.post("/approve-statement")
async def approve_statement(
    request: ApproveStatementRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Lock the statement and generate the technical file pack.

    Generates the interaction section for interactive problems and the scoring
    section when groups or points are enabled, then builds and stores the files.
    On failure the session is moved to the FAILED stage.
    """
    session = await get_session_or_404(db, request.session_id, user_id)

    if session.stage not in (PipelineStage.STATEMENT, PipelineStage.FAILED):
        raise HTTPException(400, f"Нельзя одобрить условие на этапе '{session.stage}'")

    session.stage = PipelineStage.FILES_REVIEW
    session.progress = {"status": "generating_files",
                        "current_step": "Генерация технических файлов..."}
    session.updated_at = now_utc()
    await db.commit()

    try:
        if request.problem_settings:
            session.problem_settings = {
                **(session.problem_settings or {}), **request.problem_settings,
            }
            flag_modified(session, "problem_settings")

        problem_settings = session.problem_settings or {}
        stmt = dict(session.statement or {})
        stmt_changed = False

        if is_interactive(session) and not stmt.get("interaction"):
            stmt["interaction"] = await interaction_gen.generate(stmt, session.model)
            stmt_changed = True

        if (problem_settings.get("enable_groups") or problem_settings.get("enable_points")) \
                and not stmt.get("scoring"):
            stmt["scoring"] = await scoring_gen.generate(
                stmt, session.model,
                enable_groups=bool(problem_settings.get("enable_groups")),
                enable_points=bool(problem_settings.get("enable_points")),
                problem_type=session.problem_type,
            )
            stmt_changed = True

        if stmt_changed:
            session.statement = stmt
            flag_modified(session, "statement")

        tech_data = await file_gen.generate_pack(
            session.problem_type, stmt, session.model
        )
        await upsert_all_ai_files(db, session.id, tech_data, uploaded=False)

        session.progress = {"status": "files_ready",
                            "current_step": "Файлы готовы к проверке"}
        session.updated_at = now_utc()
        await db.commit()
        await db.refresh(session)

        generated_sections = []
        if stmt.get("interaction"):
            generated_sections.append("Взаимодействие")
        if stmt.get("scoring"):
            generated_sections.append("Система оценки")

        return {
            "session_id": session.id,
            "stage": session.stage,
            "technical_data": tech_data,
            "statement": session.statement,
            "generated_sections": generated_sections,
        }

    except Exception as e:
        session.stage = PipelineStage.FAILED
        session.progress = {"status": "failed", "error": str(e),
                            "current_step": "Ошибка генерации файлов"}
        session.updated_at = now_utc()
        await db.commit()
        raise HTTPException(500, f"Ошибка генерации файлов: {e}")
