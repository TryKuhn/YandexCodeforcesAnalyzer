"""POST /add-custom-solution — register a new empty custom solution slot."""
import uuid

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import AddCustomSolutionRequest
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.ai_file_helpers import upsert_ai_file
from api.user.gpt.services.sessions import get_session_or_404, now_utc
from app.database import get_db


@gpt_router.post("/add-custom-solution")
async def add_custom_solution(
    request: AddCustomSolutionRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register a new empty custom solution slot with a generated file key."""
    session = await get_session_or_404(db, request.session_id, user_id)

    file_type = f"sol_custom_{uuid.uuid4().hex[:8]}"
    name = request.name if request.name.endswith(".cpp") else request.name + ".cpp"

    meta = dict(session.solution_meta or {})
    meta[file_type] = {"tag": request.tag, "name": name}
    session.solution_meta = meta

    await upsert_ai_file(db, session.id, file_type, "", uploaded=False, solution_meta=meta)
    session.updated_at = now_utc()
    await db.commit()

    return {
        "session_id": session.id,
        "file_type": file_type,
        "name": name,
        "tag": request.tag,
        "solution_meta": meta,
    }
