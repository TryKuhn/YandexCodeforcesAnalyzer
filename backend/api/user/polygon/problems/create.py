"""Route for creating a new (clean) Polygon problem."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.polygon_task import CreatePolygonProblemRequest
from api.user.polygon.methods import create_problem
from app.database import get_db

router = APIRouter()


@router.post("/")
async def route_create_problem(
    body: CreatePolygonProblemRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create an empty problem on Polygon.

    The AI workspace of the problem lives in the AI authoring service and is
    created there when the problem is first opened.
    """
    polygon_id = await create_problem(body.name, user_id, db)
    return {"polygon_id": polygon_id, "name": body.name}
