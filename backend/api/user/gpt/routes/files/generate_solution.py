"""POST /generate-solution — AI-generate code for a (fixed or custom) solution."""
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import RefineFileRequest
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.ai_file_helpers import upsert_ai_file
from api.user.gpt.services.files.file_registry import get_spec, solution_tag
from api.user.gpt.services.generation import solution_gen
from api.user.gpt.services.sessions import get_session_or_404, now_utc
from app.database import get_db


@gpt_router.post("/generate-solution")
async def generate_solution(
    request: RefineFileRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI-generate code for a solution slot.

    A ``file_key`` present in ``solution_meta`` is a custom solution; otherwise
    it must be a fixed solution slot (e.g. ``solution_cpp``, ``wa_sol``).
    """
    session = await get_session_or_404(db, request.session_id, user_id)
    if not session.statement:
        raise HTTPException(400, "Условие ещё не создано")

    file_key = request.file_key
    solution_meta = session.solution_meta or {}
    meta = solution_meta.get(file_key)
    spec = get_spec(file_key)

    if meta:
        tag = meta.get("tag", "OK")
        name = meta.get("name", file_key)
    elif spec and spec.category == "solution":
        tag = solution_tag(file_key) or "OK"
        name = spec.filename
    else:
        raise HTTPException(400, f"Файл '{file_key}' не найден")

    code = await solution_gen.generate_for_tag(tag, name, session.statement, session.model)

    await upsert_ai_file(
        db, session.id, file_key, code, uploaded=False, solution_meta=solution_meta
    )
    session.updated_at = now_utc()
    await db.commit()

    return {"session_id": session.id, "file_key": file_key, "new_code": code}
