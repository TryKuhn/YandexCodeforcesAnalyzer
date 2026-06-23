"""POST /refine-file — AI edit of a single technical file."""
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import RefineFileRequest
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.ai_file_helpers import (get_session_files,
                                                   upsert_ai_file)
from api.user.gpt.services.generation import file_gen
from api.user.gpt.services.sessions import (get_session_or_404, is_interactive,
                                            now_utc)
from app.database import get_db


@gpt_router.post("/refine-file")
async def refine_file(
    request: RefineFileRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """AI-edit a single technical file using the user's feedback and save the result."""
    session = await get_session_or_404(db, request.session_id, user_id)

    file_obj = (await get_session_files(db, session.id)).get(request.file_key)
    if file_obj is None:
        raise HTTPException(400, f"Файл '{request.file_key}' не найден в сессии")

    new_code = await file_gen.refine(
        file_type=request.file_key,
        current_code=file_obj.content,
        feedback=request.feedback,
        statement=session.statement,
        model=session.model,
        interactive=is_interactive(session),
    )

    await upsert_ai_file(db, session.id, request.file_key, new_code, uploaded=False)
    session.updated_at = now_utc()
    await db.commit()

    return {
        "session_id": session.id,
        "file_key": request.file_key,
        "new_code": new_code,
        "stage": session.stage,
    }
