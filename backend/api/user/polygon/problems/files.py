"""Routes for problem files: resources/sources/aux, solutions, checker,
validator, interactor and their tests, generation scripts."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.polygon_task import (
    EditSolutionExtraTagsRequest, SaveCheckerTestRequest, SaveFileRequest,
    SaveScriptRequest, SaveSolutionRequest, SaveValidatorTestRequest,
    SetCheckerRequest, SetInteractorRequest, SetValidatorRequest)
from api.user.polygon.cache import refresh_solutions
from api.user.polygon.client import PolygonAPIError, PolygonParamError
from api.user.polygon.methods import (
    clear_script, edit_solution_extra_tags, get_checker, get_checker_tests,
    get_extra_validators, get_files, get_interactor, get_script, get_validator,
    get_validator_tests, save_checker_test, save_file, save_script,
    save_solution, save_validator_test, set_checker, upload_checker, upload_interactor,
    upload_validator, view_file, view_solution)
from app.database import get_db

router = APIRouter()


def _not_found(e: PolygonAPIError) -> HTTPException:
    return HTTPException(status_code=404, detail=f"Polygon: {e.message}")


# --- files -------------------------------------------------------------------
@router.get("/{polygon_id}/files")
async def route_get_files(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the problem's files merged with its solutions list."""
    result = dict(await get_files(polygon_id, user_id, db))
    result["solutions"] = await refresh_solutions(polygon_id, user_id, db)
    return result


@router.get("/{polygon_id}/files/content")
async def route_view_file(
    polygon_id: int,
    type: str,
    name: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a file's text content; a Polygon error (e.g. no such file) is a 404."""
    try:
        content = await view_file(polygon_id, type, name, user_id, db)
    except PolygonParamError:
        raise
    except PolygonAPIError as e:
        raise _not_found(e)
    return {"content": content}


@router.post("/{polygon_id}/files")
async def route_save_file(
    polygon_id: int,
    body: SaveFileRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save a problem file (resource/source/aux) on Polygon."""
    await save_file(
        polygon_id,
        body.type,
        body.name,
        body.content,
        user_id,
        db,
        source_type=body.source_type or None,
        check_existing=body.check_existing,
        for_types=body.for_types,
        stages=body.stages,
        assets=body.assets,
    )
    return {"ok": True}


# --- solutions ---------------------------------------------------------------
@router.get("/{polygon_id}/solutions/{name}/content")
async def route_view_solution(
    polygon_id: int,
    name: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return a solution's source; a Polygon error is a 404."""
    try:
        content = await view_solution(polygon_id, name, user_id, db)
    except PolygonAPIError as e:
        raise _not_found(e)
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
        polygon_id,
        body.name,
        body.content,
        user_id,
        db,
        tag=body.tag or None,
        source_type=body.source_type or None,
        check_existing=body.check_existing,
    )
    return {"ok": True}


@router.post("/{polygon_id}/solutions/{name}/extra-tags")
async def route_edit_solution_extra_tags(
    polygon_id: int,
    name: str,
    body: EditSolutionExtraTagsRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add or remove a solution's expected verdict for a testset or a test group."""
    await edit_solution_extra_tags(
        polygon_id,
        name,
        body.remove,
        user_id,
        db,
        testset=body.testset,
        test_group=body.test_group,
        tag=body.tag,
    )
    return {"ok": True}


# --- checker / validator / interactor ----------------------------------------
@router.get("/{polygon_id}/checker")
async def route_get_checker(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the problem's current checker."""
    return {"checker": await get_checker(polygon_id, user_id, db)}


@router.post("/{polygon_id}/checker")
async def route_set_checker(
    polygon_id: int,
    body: SetCheckerRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload the checker source and set it, or set an existing/standard one."""
    if body.content is None:
        await set_checker(polygon_id, body.name, user_id, db)
    else:
        await upload_checker(polygon_id, body.name, body.content, user_id, db)
    return {"ok": True}


@router.get("/{polygon_id}/checker/tests")
async def route_get_checker_tests(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the checker's tests."""
    return await get_checker_tests(polygon_id, user_id, db)


@router.post("/{polygon_id}/checker/tests")
async def route_save_checker_test(
    polygon_id: int,
    body: SaveCheckerTestRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add or edit a checker test."""
    await save_checker_test(
        polygon_id,
        body.test_index,
        user_id,
        db,
        test_input=body.test_input,
        test_output=body.test_output,
        test_answer=body.test_answer,
        test_verdict=body.test_verdict,
        check_existing=body.check_existing,
    )
    return {"ok": True}


@router.get("/{polygon_id}/validator")
async def route_get_validator(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the problem's current validator."""
    return {"validator": await get_validator(polygon_id, user_id, db)}


@router.post("/{polygon_id}/validator")
async def route_set_validator(
    polygon_id: int,
    body: SetValidatorRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload the validator source and set it on Polygon."""
    await upload_validator(polygon_id, body.name, body.content, user_id, db)
    return {"ok": True}


@router.get("/{polygon_id}/validator/extra")
async def route_get_extra_validators(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the names of the problem's extra validators."""
    return {"extra_validators": await get_extra_validators(polygon_id, user_id, db)}


@router.get("/{polygon_id}/validator/tests")
async def route_get_validator_tests(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List the validator's tests."""
    return await get_validator_tests(polygon_id, user_id, db)


@router.post("/{polygon_id}/validator/tests")
async def route_save_validator_test(
    polygon_id: int,
    body: SaveValidatorTestRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add or edit a validator test."""
    await save_validator_test(
        polygon_id,
        body.test_index,
        user_id,
        db,
        test_input=body.test_input,
        test_verdict=body.test_verdict,
        check_existing=body.check_existing,
        test_group=body.test_group,
        testset=body.testset,
    )
    return {"ok": True}


@router.get("/{polygon_id}/interactor")
async def route_get_interactor(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the problem's current interactor."""
    return {"interactor": await get_interactor(polygon_id, user_id, db)}


@router.post("/{polygon_id}/interactor")
async def route_set_interactor(
    polygon_id: int,
    body: SetInteractorRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload the interactor source and set it on Polygon."""
    await upload_interactor(polygon_id, body.name, body.content, user_id, db)
    return {"ok": True}


# --- scripts -----------------------------------------------------------------
@router.get("/{polygon_id}/script/{testset}")
async def route_get_script(
    polygon_id: int,
    testset: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the generator script for a testset."""
    return {"content": await get_script(polygon_id, testset, user_id, db)}


@router.post("/{polygon_id}/script/{testset}")
async def route_save_script(
    polygon_id: int,
    testset: str,
    body: SaveScriptRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save the generator script for a testset on Polygon."""
    await save_script(polygon_id, testset, body.source, user_id, db)
    return {"ok": True}


@router.delete("/{polygon_id}/script/{testset}")
async def route_clear_script(
    polygon_id: int,
    testset: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Clear the generator script for a testset."""
    await clear_script(polygon_id, testset, user_id, db)
    return {"ok": True}
