"""Routes for problem source files: resources, solutions, checker, validator, and scripts."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.user.polygon.get_response import PolygonAPIError
from api.pydantic_schemas.user.polygon_task import (
    SaveFileRequest,
    SaveSolutionRequest,
    SaveScriptRequest,
    SetCheckerRequest,
    SetValidatorRequest,
)
from api.user.polygon.files.checker.get.checker import get_checker
from api.user.polygon.files.checker.post.set_checker import set_checker
from api.user.polygon.files.get.files import get_files
from api.user.polygon.files.get.view_file import view_file
from api.user.polygon.files.post.save_file import save_file
from api.user.polygon.files.script.get.script import get_script
from api.user.polygon.files.script.post.save_script import save_script
from api.user.polygon.files.solution.get.solutions import get_solutions
from api.user.polygon.files.solution.get.view_solution import view_solution
from api.user.polygon.files.solution.post.save_solution import save_solution
from api.user.polygon.files.validator.get.validator import get_validator
from api.user.polygon.files.validator.post.set_validator import set_validator
from app.database import get_db

router = APIRouter()


@router.get("/{polygon_id}/files")
async def route_get_files(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the problem's files merged with its solutions list."""
    files_data = await get_files(problem_id=polygon_id, user_id=user_id, db=db)
    solutions = await get_solutions(problem_id=polygon_id, user_id=user_id, db=db)
    result = {}
    if isinstance(files_data, dict):
        result.update(files_data)
    result["solutions"] = solutions if isinstance(solutions, list) else []
    return result


@router.get("/{polygon_id}/files/content")
async def route_view_file(
    polygon_id: int,
    type: str,
    name: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a file's content; map a Polygon API error to a 404."""
    try:
        content = await view_file(
            problem_id=polygon_id, file_type=type, name=name, user_id=user_id, db=db
        )
    except PolygonAPIError as e:
        raise HTTPException(status_code=404, detail=f"Polygon: {e.message}")
    return {"content": content}


@router.post("/{polygon_id}/files")
async def route_save_file(
    polygon_id: int,
    body: SaveFileRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save a problem file (source/resource) on Polygon."""
    await save_file(
        problem_id=polygon_id,
        file_type=body.type,
        name=body.name,
        file_content=body.content,
        user_id=user_id,
        db=db,
        source_type=body.source_type,
        check_existing=body.check_existing,
    )
    return {"ok": True}


@router.get("/{polygon_id}/solutions/{name}/content")
async def route_view_solution(
    polygon_id: int,
    name: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a solution's content; map a Polygon API error to a 404."""
    try:
        content = await view_solution(problem_id=polygon_id, name=name, user_id=user_id, db=db)
    except PolygonAPIError as e:
        raise HTTPException(status_code=404, detail=f"Polygon: {e.message}")
    return {"content": content}


@router.post("/{polygon_id}/solutions")
async def route_save_solution(
    polygon_id: int,
    body: SaveSolutionRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save a solution with its tag on Polygon."""
    await save_solution(
        problem_id=polygon_id,
        name=body.name,
        file_content=body.content,
        tag=body.tag,
        user_id=user_id,
        db=db,
        source_type=body.source_type,
    )
    return {"ok": True}


@router.get("/{polygon_id}/checker")
async def route_get_checker(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the problem's current checker."""
    checker = await get_checker(problem_id=polygon_id, user_id=user_id, db=db)
    return {"checker": checker}


@router.post("/{polygon_id}/checker")
async def route_set_checker(
    polygon_id: int,
    body: SetCheckerRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload and set the problem's checker on Polygon."""
    await set_checker(
        problem_id=polygon_id,
        name=body.name,
        file_content=body.content,
        user_id=user_id,
        db=db,
    )
    return {"ok": True}


@router.get("/{polygon_id}/validator")
async def route_get_validator(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the problem's current validator."""
    validator = await get_validator(problem_id=polygon_id, user_id=user_id, db=db)
    return {"validator": validator}


@router.post("/{polygon_id}/validator")
async def route_set_validator(
    polygon_id: int,
    body: SetValidatorRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload and set the problem's validator on Polygon."""
    await set_validator(
        problem_id=polygon_id,
        name=body.name,
        file_content=body.content,
        user_id=user_id,
        db=db,
    )
    return {"ok": True}


@router.get("/{polygon_id}/script/{testset}")
async def route_get_script(
    polygon_id: int,
    testset: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the generator script for a testset."""
    content = await get_script(problem_id=polygon_id, testset=testset, user_id=user_id, db=db)
    return {"content": content}


@router.post("/{polygon_id}/script/{testset}")
async def route_save_script(
    polygon_id: int,
    testset: str,
    body: SaveScriptRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save the generator script for a testset on Polygon."""
    await save_script(
        problem_id=polygon_id, testset=testset, source=body.source, user_id=user_id, db=db
    )
    return {"ok": True}
