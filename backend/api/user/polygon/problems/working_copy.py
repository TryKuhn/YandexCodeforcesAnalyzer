"""Routes for the problem's working copy: update, discard, commit."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.polygon_task import CommitRequest
from api.user.polygon.methods import (commit_changes, discard_working_copy,
                                      update_working_copy)
from app.database import get_db

router = APIRouter()


@router.post("/{polygon_id}/working-copy/update")
async def route_update_working_copy(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Bring the working copy up to date with the latest revision."""
    await update_working_copy(polygon_id, user_id, db)
    return {"ok": True}


@router.post("/{polygon_id}/working-copy/discard")
async def route_discard_working_copy(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Drop all uncommitted changes."""
    await discard_working_copy(polygon_id, user_id, db)
    return {"ok": True}


@router.post("/{polygon_id}/commit")
async def route_commit(
    polygon_id: int,
    body: CommitRequest = CommitRequest(),
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Commit the working copy (409 on a conflict)."""
    return await commit_changes(
        polygon_id, user_id, db, minor_changes=body.minor_changes, message=body.message
    )
