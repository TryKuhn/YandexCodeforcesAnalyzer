"""Routes for problem materials."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.polygon_task import SaveMaterialRequest
from api.user.polygon.methods import (get_materials, remove_material,
                                      save_material)
from app.database import get_db

router = APIRouter()


@router.get("/{polygon_id}/materials")
async def route_get_materials(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the problem's materials."""
    return await get_materials(polygon_id, user_id, db)


@router.put("/{polygon_id}/materials/{name}")
async def route_save_material(
    polygon_id: int,
    name: str,
    body: SaveMaterialRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create or update a material (needs a commit to take effect)."""
    await save_material(
        polygon_id,
        name,
        body.publish_strategy,
        body.items,
        user_id,
        db,
        original_name=body.original_name,
    )
    return {"ok": True}


@router.delete("/{polygon_id}/materials/{name}")
async def route_remove_material(
    polygon_id: int,
    name: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Remove a material (needs a commit to take effect)."""
    await remove_material(polygon_id, name, user_id, db)
    return {"ok": True}
