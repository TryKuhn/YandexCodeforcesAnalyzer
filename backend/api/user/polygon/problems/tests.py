"""Routes for testsets: test lists, input/answer content, previews, saving,
deleting and grouping tests."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.polygon_task import (SaveTestRequest,
                                                    SetTestGroupRequest,
                                                    TestIndicesRequest,
                                                    UpdateTestRequest)
from api.user.polygon.methods import (delete_tests, get_test_answer,
                                      get_test_input, get_tests, preview_tests,
                                      save_test, set_test_group)
from app.database import get_db

router = APIRouter()


@router.get("/{polygon_id}/tests/{testset}")
async def route_get_tests(
    polygon_id: int,
    testset: str,
    no_inputs: bool = False,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List tests for a testset; set no_inputs to omit test input bodies."""
    return await get_tests(polygon_id, testset, user_id, db, no_inputs=no_inputs)


@router.get("/{polygon_id}/tests/{testset}/preview")
async def route_preview_tests(
    polygon_id: int,
    testset: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Polygon's test previews (input/answer may be missing while generating)."""
    return await preview_tests(polygon_id, testset, user_id, db)


@router.post("/{polygon_id}/tests/{testset}")
async def route_create_or_update_test(
    polygon_id: int,
    testset: str,
    body: SaveTestRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Add or edit a test with the full set of ``problem.saveTest`` options."""
    await save_test(
        polygon_id,
        testset,
        body.test_index,
        body.test_input,
        user_id,
        db,
        check_existing=body.check_existing,
        test_group=body.test_group,
        test_points=body.test_points,
        test_description=body.test_description,
        test_use_in_statements=body.test_use_in_statements,
        test_input_for_statements=body.test_input_for_statements,
        test_output_for_statements=body.test_output_for_statements,
        verify_input_output_for_statements=body.verify_input_output_for_statements,
    )
    return {"ok": True}


@router.post("/{polygon_id}/tests/{testset}/delete")
async def route_delete_tests(
    polygon_id: int,
    testset: str,
    body: TestIndicesRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete tests; Polygon deletes nothing if any of them fails its pre-check."""
    await delete_tests(polygon_id, testset, body.test_indices, user_id, db)
    return {"ok": True}


@router.post("/{polygon_id}/tests/{testset}/group")
async def route_set_test_group(
    polygon_id: int,
    testset: str,
    body: SetTestGroupRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Move tests into a group (groups must be enabled for the testset)."""
    await set_test_group(polygon_id, testset, body.test_group, body.test_indices, user_id, db)
    return {"ok": True}


@router.get("/{polygon_id}/tests/{testset}/{index}/input")
async def route_get_test_input(
    polygon_id: int,
    testset: str,
    index: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the input content of a single test."""
    return {"content": await get_test_input(polygon_id, testset, index, user_id, db)}


@router.get("/{polygon_id}/tests/{testset}/{index}/preview")
async def route_get_test_preview(
    polygon_id: int,
    testset: str,
    index: int,
    limit: int = 400,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Short input/output preview for a quick inline peek (truncated to ``limit``
    chars each) — so the UI doesn't load/render the full test for a glance."""
    inp = await get_test_input(polygon_id, testset, index, user_id, db)
    out = await get_test_answer(polygon_id, testset, index, user_id, db)
    return {
        "input": inp[:limit],
        "output": out[:limit],
        "input_truncated": len(inp) > limit,
        "output_truncated": len(out) > limit,
    }


@router.get("/{polygon_id}/tests/{testset}/{index}/answer")
async def route_get_test_answer(
    polygon_id: int,
    testset: str,
    index: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the jury answer content of a single test."""
    return {"content": await get_test_answer(polygon_id, testset, index, user_id, db)}


@router.patch("/{polygon_id}/tests/{testset}/{index}")
async def route_save_test(
    polygon_id: int,
    testset: str,
    index: int,
    body: UpdateTestRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Replace the input of an existing test at ``index``."""
    await save_test(
        polygon_id, testset, index, body.test_input, user_id, db, check_existing=False
    )
    return {"ok": True}
