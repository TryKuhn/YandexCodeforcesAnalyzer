"""Routes for scoring settings: groups, points and test-group policies."""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.polygon_task import (EnableGroupsBody,
                                                    EnablePointsBody,
                                                    SaveTestGroupRequest)
from api.user.polygon.methods import (
    enable_groups, enable_points, enable_treat_points_from_checker_as_percent,
    save_test_group, view_test_group)
from app.database import get_db

router = APIRouter()

__all__ = ["router", "EnableGroupsBody", "EnablePointsBody"]


@router.post("/{polygon_id}/settings/enable-groups")
async def route_enable_groups(
    polygon_id: int,
    body: EnableGroupsBody,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable test groups for the given testset on Polygon."""
    await enable_groups(polygon_id, body.testset, body.enable, user_id, db)
    return {"ok": True}


@router.post("/{polygon_id}/settings/enable-points")
async def route_enable_points(
    polygon_id: int,
    body: EnablePointsBody,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable per-test points for the problem on Polygon."""
    await enable_points(polygon_id, body.enable, user_id, db)
    return {"ok": True}


@router.post("/{polygon_id}/settings/treat-points-from-checker-as-percent")
async def route_enable_treat_points_as_percent(
    polygon_id: int,
    body: EnablePointsBody,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Treat checker-reported points as a percentage (points must be enabled)."""
    await enable_treat_points_from_checker_as_percent(polygon_id, body.enable, user_id, db)
    return {"ok": True}


@router.get("/{polygon_id}/groups/{testset}")
async def route_view_test_groups(
    polygon_id: int,
    testset: str,
    group: Optional[str] = None,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the testset's groups (or one ``group``) with their policies."""
    return await view_test_group(polygon_id, testset, user_id, db, group=group)


@router.put("/{polygon_id}/groups/{testset}/{group}")
async def route_save_test_group(
    polygon_id: int,
    testset: str,
    group: str,
    body: SaveTestGroupRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a group's points/feedback policies and dependencies."""
    await save_test_group(
        polygon_id,
        testset,
        group,
        user_id,
        db,
        points_policy=body.points_policy,
        feedback_policy=body.feedback_policy,
        dependencies=body.dependencies,
    )
    return {"ok": True}
