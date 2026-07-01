"""POST /generate-solution-code — AI-generate code for a user-defined solution.

Used by the "Сгенерировать с ИИ" button in the add-solution form: the user
picks a tag + name (+ an optional free-form hint) and gets back solution code to
review before uploading. Unlike ``/generate-solution`` this does not require a
pre-existing file slot in ``solution_meta``.
"""
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import GenerateSolutionCodeRequest
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.chat.file_context import ensure_files_loaded
from api.user.gpt.services.generation import solution_gen
from api.user.gpt.services.sessions import get_session_or_404
from app.database import get_db


@gpt_router.post("/generate-solution-code")
async def generate_solution_code(
    request: GenerateSolutionCodeRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate solution code for an arbitrary tag/name; returns code only."""
    session = await get_session_or_404(db, request.session_id, user_id)
    # Pull the statement (and files) from Polygon if the session hasn't yet, so
    # imported problems can generate solutions without a manual sync first.
    await ensure_files_loaded(db, session)
    if not session.statement:
        raise HTTPException(400, "Условие ещё не создано")

    tag = (request.tag or "OK").strip() or "OK"
    name = (request.name or "solution.cpp").strip() or "solution.cpp"

    code = await solution_gen.generate_for_tag(
        tag, name, session.statement, session.model, instruction=request.instruction
    )
    return {"session_id": session.id, "tag": tag, "name": name, "code": code}
