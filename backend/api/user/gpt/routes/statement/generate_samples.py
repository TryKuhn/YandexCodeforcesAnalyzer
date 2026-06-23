"""POST /generate-samples — AI sample tests for the statement."""
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import GenerateSamplesRequest
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.generation import samples_gen
from api.user.gpt.services.sessions import get_session_or_404, now_utc
from app.database import get_db


@gpt_router.post("/generate-samples")
async def generate_samples(
    request: GenerateSamplesRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate AI sample tests for the statement and store them as examples."""
    session = await get_session_or_404(db, request.session_id, user_id)
    if not session.statement:
        raise HTTPException(400, "Условие ещё не создано")

    examples = await samples_gen.generate(
        session.statement, session.model, count=request.count or 3
    )
    indexed = [
        {"index": i + 1, "input": ex["input"], "output": ex["output"]}
        for i, ex in enumerate(examples)
    ]
    session.examples = indexed
    session.updated_at = now_utc()
    await db.commit()
    return {"session_id": session.id, "examples": indexed}
