"""Routes for a problem's cautions and issues."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.polygon_task import (AddIssueRequest,
                                                    UpdateIssueRequest)
from api.user.polygon.methods import (add_issue, get_cautions, get_issues,
                                      update_issue)
from app.database import get_db

router = APIRouter()


@router.get("/{polygon_id}/cautions")
async def route_get_cautions(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Polygon's warnings about the problem and package readiness."""
    return await get_cautions(polygon_id, user_id, db)


@router.get("/{polygon_id}/issues")
async def route_get_issues(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List issues, most recently modified first."""
    return await get_issues(polygon_id, user_id, db)


@router.post("/{polygon_id}/issues")
async def route_add_issue(
    polygon_id: int,
    body: AddIssueRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Open a new issue; returns it."""
    return await add_issue(
        polygon_id, body.type, body.content, user_id, db, assignee=body.assignee
    )


@router.patch("/{polygon_id}/issues/{issue_id}")
async def route_update_issue(
    polygon_id: int,
    issue_id: int,
    body: UpdateIssueRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Comment on / close / reopen / reassign an issue; returns it."""
    return await update_issue(
        polygon_id,
        issue_id,
        user_id,
        db,
        comment=body.comment,
        status=body.status,
        issue_type=body.type,
        assignee=body.assignee,
    )
