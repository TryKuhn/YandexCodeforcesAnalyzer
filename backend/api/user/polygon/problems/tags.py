"""Routes for viewing and setting a problem's tags."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.polygon_task import UpdateTagsRequest
from api.user.polygon.problem.get.tags import view_tags
from api.user.polygon.problem.settings.set_tags import set_tags
from app.database import get_db

router = APIRouter()


@router.get("/{polygon_id}/tags")
async def route_get_tags(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the problem's tags from Polygon."""
    tags = await view_tags(problem_id=polygon_id, user_id=user_id, db=db)
    return {"tags": tags}


@router.patch("/{polygon_id}/tags")
async def route_set_tags(
    polygon_id: int,
    body: UpdateTagsRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set the problem's tags on Polygon (sent as a comma-separated string)."""
    await set_tags(
        problem_id=polygon_id,
        tags=",".join(body.tags),
        user_id=user_id,
        db=db,
    )
    return {"ok": True}
