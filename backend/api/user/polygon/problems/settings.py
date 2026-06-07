from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.user.polygon.problem.settings.enable_groups import enable_groups
from api.user.polygon.problem.settings.enable_points import enable_points
from app.database import get_db

router = APIRouter()


class EnableGroupsBody(BaseModel):
    enable: bool
    testset: str = "tests"


class EnablePointsBody(BaseModel):
    enable: bool


@router.post("/{polygon_id}/settings/enable-groups")
async def route_enable_groups(
    polygon_id: int,
    body: EnableGroupsBody,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await enable_groups(
        problem_id=polygon_id,
        test_set=body.testset,
        enable=body.enable,
        user_id=user_id,
        db=db,
    )
    return {"ok": True}


@router.post("/{polygon_id}/settings/enable-points")
async def route_enable_points(
    polygon_id: int,
    body: EnablePointsBody,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await enable_points(
        problem_id=polygon_id,
        enable=body.enable,
        user_id=user_id,
        db=db,
    )
    return {"ok": True}
