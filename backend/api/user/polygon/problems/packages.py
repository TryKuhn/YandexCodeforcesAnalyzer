from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.user.polygon.problem.get.packages import get_packages
from api.user.polygon.problem.post.commit import commit_changes
from api.user.polygon.problem.post.package import build_package
from app.database import get_db

router = APIRouter()


class BuildPackageRequest(BaseModel):
    full: Optional[bool] = False
    verify: Optional[bool] = False


@router.get("/{polygon_id}/packages")
async def route_get_packages(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await get_packages(problem_id=polygon_id, user_id=user_id, db=db)


@router.post("/{polygon_id}/packages/build")
async def route_build_package(
    polygon_id: int,
    body: BuildPackageRequest = BuildPackageRequest(),
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await commit_changes(
        problem_id=polygon_id,
        user_id=user_id,
        db=db,
        minor_changes=True,
        message="manual commit",
    )
    await build_package(problem_id=polygon_id, user_id=user_id, db=db)
    return {"status": "building"}
