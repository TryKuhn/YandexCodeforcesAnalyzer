"""Routes for a problem's note, general description/tutorial and access list."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.polygon_task import (
    SaveGeneralDescriptionRequest, SaveGeneralTutorialRequest, SaveNoteRequest,
    SetAccessRequest)
from api.user.polygon.methods import (get_accesses, get_note,
                                      save_general_description,
                                      save_general_tutorial, save_note,
                                      set_access, view_general_description,
                                      view_general_tutorial)
from app.database import get_db

router = APIRouter()


@router.get("/{polygon_id}/note")
async def route_get_note(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the problem's short note."""
    return {"note": await get_note(polygon_id, user_id, db)}


@router.put("/{polygon_id}/note")
async def route_save_note(
    polygon_id: int,
    body: SaveNoteRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set the note (empty clears it); does not touch the working copy."""
    await save_note(polygon_id, body.note, user_id, db)
    return {"ok": True}


@router.get("/{polygon_id}/general-description")
async def route_get_general_description(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the problem's general description."""
    return {"description": await view_general_description(polygon_id, user_id, db)}


@router.put("/{polygon_id}/general-description")
async def route_save_general_description(
    polygon_id: int,
    body: SaveGeneralDescriptionRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save the problem's general description."""
    await save_general_description(polygon_id, body.description, user_id, db)
    return {"ok": True}


@router.get("/{polygon_id}/general-tutorial")
async def route_get_general_tutorial(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the problem's general tutorial."""
    return {"tutorial": await view_general_tutorial(polygon_id, user_id, db)}


@router.put("/{polygon_id}/general-tutorial")
async def route_save_general_tutorial(
    polygon_id: int,
    body: SaveGeneralTutorialRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save the problem's general tutorial."""
    await save_general_tutorial(polygon_id, body.tutorial, user_id, db)
    return {"ok": True}


@router.get("/{polygon_id}/accesses")
async def route_get_accesses(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Who has access to the problem (requires WRITE/OWNER)."""
    return await get_accesses(polygon_id, user_id, db)


@router.post("/{polygon_id}/accesses")
async def route_set_access(
    polygon_id: int,
    body: SetAccessRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Grant READ/WRITE to a user or revoke it with NONE."""
    await set_access(polygon_id, body.login, body.access_type, user_id, db)
    return {"ok": True}
