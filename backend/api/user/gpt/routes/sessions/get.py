"""GET /session/{session_id} — full session state for page load."""
import json

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.ai_file_helpers import get_all_file_contents
from api.user.gpt.services.sessions import get_session_or_404
from app.database import get_db


def _reconstruct_chat_log_from_history(history: list) -> list:
    """Build a human-readable chat_log from raw LLM history for legacy sessions."""
    entries = []
    for i, msg in enumerate(history or []):
        role = msg.get("role", "")
        if role == "system":
            continue
        content = msg.get("content", "") or ""
        if role == "assistant" and content.lstrip().startswith("{"):
            try:
                data = json.loads(content)
                if isinstance(data, dict) and "name" in data:
                    content = f"Условие обновлено: «{data['name']}»"
                elif isinstance(data, dict):
                    content = "Ответ получен (JSON)"
            except (json.JSONDecodeError, TypeError):
                pass
        entries.append(
            {"id": f"hist-{i}", "role": role, "content": content[:3000], "timestamp": ""}
        )
    return entries


@gpt_router.get("/session/{session_id}")
async def get_session(
    session_id: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the full session state for page load, reconstructing chat_log for legacy sessions."""
    session = await get_session_or_404(db, session_id, user_id)

    chat_log = session.chat_log or []
    if not chat_log and session.history:
        chat_log = _reconstruct_chat_log_from_history(session.history)

    return {
        "session_id": session.id,
        "stage": session.stage,
        "problem_type": session.problem_type,
        "statement": session.statement,
        "technical_data": await get_all_file_contents(db, session_id),
        "history": session.history or [],
        "chat_log": chat_log,
        "model": session.model,
        "system_prompt": session.system_prompt,
        "progress": session.progress or {"status": "idle"},
        "upload_errors": session.upload_errors or {},
        "polygon_problem_id": session.polygon_problem_id,
        "problem_settings": session.problem_settings or {},
        "solution_meta": session.solution_meta or {},
        "examples": session.examples or [],
    }
