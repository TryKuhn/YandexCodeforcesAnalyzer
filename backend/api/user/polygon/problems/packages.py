"""Routes for listing, building and downloading Polygon problem packages."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.polygon_task import BuildPackageRequest
from api.user.polygon.methods import (build_package, commit_changes,
                                      download_package, get_packages)
from app.database import get_db

router = APIRouter()

__all__ = ["router", "BuildPackageRequest"]


@router.get("/{polygon_id}/packages")
async def route_get_packages(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the problem's packages from Polygon."""
    return await get_packages(polygon_id, user_id, db)


@router.post("/{polygon_id}/packages/build")
async def route_build_package(
    polygon_id: int,
    body: BuildPackageRequest = BuildPackageRequest(),
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Commit pending changes (unless ``commit=false``), then start a build
    with the requested ``full``/``verify`` flags."""
    if body.commit:
        await commit_changes(
            polygon_id, user_id, db, minor_changes=True, message="manual commit"
        )
    await build_package(polygon_id, user_id, db, full=body.full, verify=body.verify)
    return {"status": "building"}


@router.get("/{polygon_id}/packages/{package_id}/download")
async def route_download_package(
    polygon_id: int,
    package_id: int,
    type: str = "standard",
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Download a built package archive (standard / linux / windows)."""
    content = await download_package(polygon_id, package_id, user_id, db, package_type=type)
    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Content-Disposition":
                f'attachment; filename="problem-{polygon_id}-{package_id}-{type}.zip"'
        },
    )
