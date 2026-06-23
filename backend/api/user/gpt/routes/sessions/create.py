"""POST /create-session — create a session, optionally generating a statement."""
from fastapi import Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import (AIStatementRequest,
                                               AIStatementResponse)
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.generation import statement_gen
from api.user.gpt.services.llm.models import normalize_model
from api.user.gpt.services.sessions import new_id, now_utc
from app.database import get_db
from models.task.session import PipelineStage, ProblemType, TaskSession

DEFAULT_SETTINGS = {
    "input_file": "stdin",
    "output_file": "stdout",
    "interactive": False,
    "time_limit": 2000,
    "memory_limit": 256,
    "tags": [],
    "enable_groups": False,
    "enable_points": False,
}


@gpt_router.post("/create-session")
async def create_session(
    request: AIStatementRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new task session, generating an initial statement if an idea is given."""
    ts = now_utc()
    idea = (request.idea or "").strip()
    model = normalize_model(request.model)

    statement_data = None
    if idea:
        try:
            statement_data = await statement_gen.generate(
                user_idea=idea,
                model=model,
                user_prompt=request.user_prompt or "",
                history=request.history or [],
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Ошибка генерации условия: {e}")

    session = TaskSession(
        id=new_id(),
        user_id=user_id,
        model=model,
        system_prompt=request.user_prompt or "",
        statement=statement_data,
        history=request.history or [],
        problem_type=ProblemType.REGULAR,
        stage=PipelineStage.STATEMENT,
        progress={"status": "idle"},
        problem_settings=dict(DEFAULT_SETTINGS),
        solution_meta={},
        examples=[],
        created_at=ts,
        updated_at=ts,
    )
    db.add(session)
    await db.commit()

    if statement_data is None:
        return {
            "session_id": session.id,
            "statement": None,
            "stage": PipelineStage.STATEMENT,
        }
    return AIStatementResponse(
        statement=statement_data,
        session_id=session.id,
        stage=PipelineStage.STATEMENT,
    )
