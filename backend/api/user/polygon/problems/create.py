import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.polygon_task import CreatePolygonProblemRequest
from api.user.polygon.problem.post.create import create_problem
from app.database import get_db
from models.task.session import PipelineStage, TaskSession

router = APIRouter()


@router.post("/")
async def route_create_problem(
    body: CreatePolygonProblemRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    polygon_id = await create_problem(name=body.name, user_id=user_id, db=db)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    session = TaskSession(
        id=str(uuid.uuid4()),
        user_id=user_id,
        model="anthropic/claude-opus-4.7",
        system_prompt="",
        history=[],
        stage=PipelineStage.STATEMENT,
        progress={"status": "idle"},
        statement=None,
        problem_settings={
            "input_file": "stdin",
            "output_file": "stdout",
            "interactive": False,
            "time_limit": 2000,
            "memory_limit": 256,
            "tags": [],
            "enable_groups": False,
            "enable_points": False,
        },
        polygon_problem_id=polygon_id,
        created_at=now,
        updated_at=now,
    )
    db.add(session)
    await db.commit()

    return {"polygon_id": polygon_id, "name": body.name, "session_id": session.id}
