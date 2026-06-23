"""POST /manual-fix-file — save a user's manual edit of a file."""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import ManualFixRequest
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.ai_file_helpers import upsert_ai_file
from api.user.gpt.services.sessions import get_session_or_404, now_utc
from app.database import get_db


@gpt_router.post("/manual-fix-file")
async def manual_fix_file(
    request: ManualFixRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save a user's manual edit of a file and clear any upload error for that key."""
    session = await get_session_or_404(db, request.session_id, user_id)

    await upsert_ai_file(
        db, session.id, request.file_key, request.new_content, uploaded=False
    )

    upload_errors = dict(session.upload_errors or {})
    upload_errors.pop(request.file_key, None)
    session.upload_errors = upload_errors
    session.updated_at = now_utc()
    await db.commit()

    return {
        "session_id": session.id,
        "file_key": request.file_key,
        "stage": session.stage,
        "remaining_errors": list(upload_errors.keys()),
    }
