"""POST /session/{session_id}/sync-from-polygon — pull all files into the session.

Force-reloads the statement and every file (sources/solutions/script) from
Polygon into the session, so the AI operates on the current Polygon state.
"""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.chat.file_context import reload_from_polygon
from api.user.gpt.services.sessions import get_session_or_404
from app.database import get_db


@gpt_router.post("/session/{session_id}/sync-from-polygon")
async def sync_from_polygon(
    session_id: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Force-reload the statement and all files from Polygon into the session."""
    session = await get_session_or_404(db, session_id, user_id)
    result = await reload_from_polygon(db, session)
    return {"session_id": session_id, **result}
