"""POST /import-from-polygon — new session from an existing Polygon statement."""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import ImportFromPolygonRequest
from api.user.gpt.base_gpt import gpt_router
from api.user.gpt.services.llm.models import normalize_model
from api.user.gpt.services.sessions import new_id, now_utc
from api.user.polygon.statement.get.setatement import get_statements
from app.database import get_db
from models.task.session import PipelineStage, ProblemType, TaskSession


def _extract_statement(raw) -> dict:
    """Pick the russian/english (or first) statement and normalize its fields."""
    data: dict = (
        raw.get("russian") or raw.get("english") or next(iter(raw.values()), {})
        if isinstance(raw, dict) else {}
    )
    return {
        "name": data.get("name", ""),
        "legend": data.get("legend", ""),
        "input": data.get("input", ""),
        "output": data.get("output", ""),
        "notes": data.get("notes") or "",
        "tutorial": data.get("tutorial") or "",
    }


@gpt_router.post("/import-from-polygon")
async def import_from_polygon(
    request: ImportFromPolygonRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new task session seeded from an existing Polygon statement."""
    raw = await get_statements(request.polygon_problem_id, user_id, db)
    statement = _extract_statement(raw)

    ts = now_utc()
    session = TaskSession(
        id=new_id(),
        user_id=user_id,
        model=normalize_model(request.model),
        system_prompt="",
        statement=statement,
        history=[],
        problem_type=ProblemType.REGULAR,
        stage=PipelineStage.STATEMENT,
        progress={"status": "idle"},
        polygon_problem_id=request.polygon_problem_id,
        created_at=ts,
        updated_at=ts,
    )
    db.add(session)
    await db.commit()

    return {
        "session_id": session.id,
        "statement": statement,
        "stage": PipelineStage.STATEMENT,
        "polygon_problem_id": request.polygon_problem_id,
    }
