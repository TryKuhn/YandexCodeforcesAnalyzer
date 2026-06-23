"""Routes for reading test lists, test input/answer content, and saving tests."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.polygon_task import UpdateTestRequest
from api.user.polygon.files.test.get.test_answer import get_test_answer
from api.user.polygon.files.test.get.test_input import get_test_input
from api.user.polygon.files.test.get.tests import get_tests
from api.user.polygon.files.test.post.save_test import save_test
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
    return await get_tests(
        problem_id=polygon_id,
        testset=testset,
        user_id=user_id,
        db=db,
        no_inputs=no_inputs,
    )


@router.get("/{polygon_id}/tests/{testset}/{index}/input")
async def route_get_test_input(
    polygon_id: int,
    testset: str,
    index: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the input content of a single test."""
    content = await get_test_input(
        problem_id=polygon_id,
        testset=testset,
        test_index=index,
        user_id=user_id,
        db=db,
    )
    return {"content": content}


@router.get("/{polygon_id}/tests/{testset}/{index}/answer")
async def route_get_test_answer(
    polygon_id: int,
    testset: str,
    index: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return the jury answer content of a single test."""
    content = await get_test_answer(
        problem_id=polygon_id,
        testset=testset,
        test_index=index,
        user_id=user_id,
        db=db,
    )
    return {"content": content}


@router.patch("/{polygon_id}/tests/{testset}/{index}")
async def route_save_test(
    polygon_id: int,
    testset: str,
    index: int,
    body: UpdateTestRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save a test's input (UTF-8 encoded) at the given index on Polygon."""
    await save_test(
        problem_id=polygon_id,
        testset=testset,
        test_index=index,
        test_input=body.test_input.encode("utf-8"),
        user_id=user_id,
        db=db,
        check_existing=False,
    )
    return {"ok": True}
