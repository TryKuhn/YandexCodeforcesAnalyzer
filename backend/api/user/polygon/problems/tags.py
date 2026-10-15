"""Routes for viewing and setting a problem's tags."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.polygon_task import UpdateTagsRequest
from api.user.polygon.methods import save_tags, view_tags
from app.database import get_db

router = APIRouter()


@router.get("/{polygon_id}/tags")
async def route_get_tags(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the problem's tags from Polygon."""
    return {"tags": await view_tags(polygon_id, user_id, db)}


@router.patch("/{polygon_id}/tags")
async def route_set_tags(
    polygon_id: int,
    body: UpdateTagsRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Replace the problem's tags on Polygon."""
    await save_tags(polygon_id, body.tags, user_id, db)
    return {"ok": True}
