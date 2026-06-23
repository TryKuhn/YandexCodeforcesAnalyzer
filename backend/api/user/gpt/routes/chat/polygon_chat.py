"""POST /polygon-chat — read-only tool agent over a Polygon problem."""
from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.chat.polygon_agent import run_agent
from api.user.gpt.services.llm.models import normalize_model
from api.user.gpt.services.sessions import get_session_or_404
from app.database import get_db


class PolygonAgentChatRequest(BaseModel):
    """Request body for the Polygon tool-agent chat.

    Each attachment is a dict of the shape ``{"type", "label", "content"}``.
    """

    session_id: str
    message: str
    model: str = "anthropic/claude-sonnet-4.6"
    attachments: list[dict] = []


@gpt_router.post("/polygon-chat")
async def polygon_agent_chat(
    request: PolygonAgentChatRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run the read-only tool agent over the session's Polygon problem."""
    session = await get_session_or_404(db, request.session_id, user_id)
    if not session.polygon_problem_id:
        raise HTTPException(status_code=404, detail="Задача ещё не создана в Polygon")

    response = await run_agent(
        db, session, user_id, request.message,
        normalize_model(request.model), request.attachments,
    )
    return {"response": response}
