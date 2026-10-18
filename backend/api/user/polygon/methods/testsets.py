"""Tests and generation scripts."""
from collections.abc import Iterable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import PolygonParamError, call


def _indices(method: str, test_indices: Iterable[int]) -> list[int]:
    indices = [int(i) for i in test_indices]
    if not indices:
        raise PolygonParamError("testIndices: список тестов пуст", method=method)
    return indices


async def get_script(problem_id: int, testset: str, user_id: int, db: AsyncSession) -> str:
    """``problem.script`` -> generation script source."""
    return await call(
        "problem.script", user_id, db, kind="text", problemId=problem_id, testset=testset
    )


async def save_script(
    problem_id: int, testset: str, source: str, user_id: int, db: AsyncSession
) -> None:
    """``problem.saveScript``."""
    await call(
        "problem.saveScript", user_id, db, problemId=problem_id, testset=testset, source=source
    )


async def clear_script(problem_id: int, testset: str, user_id: int, db: AsyncSession) -> None:
    """``problem.clearScript``."""
    await call("problem.clearScript", user_id, db, problemId=problem_id, testset=testset)


async def get_tests(
    problem_id: int,
    testset: str,
    user_id: int,
    db: AsyncSession,
    *,
    no_inputs: bool | None = None,
) -> list[dict[str, Any]]:
    """``problem.tests`` -> ``Test[]``."""
    result = await call(
        "problem.tests", user_id, db, problemId=problem_id, testset=testset, noInputs=no_inputs
    )
    return result if isinstance(result, list) else []


async def preview_tests(
    problem_id: int, testset: str, user_id: int, db: AsyncSession
) -> list[dict[str, Any]]:
    """``problem.previewTests`` -> ``TestPreview[]`` (input/answer may still be generating)."""
    result = await call("problem.previewTests", user_id, db, problemId=problem_id, testset=testset)
    return result if isinstance(result, list) else []


async def get_test_input(
    problem_id: int, testset: str, test_index: int, user_id: int, db: AsyncSession
) -> str:
    """``problem.testInput`` -> test input (manual and generated tests alike)."""
    return await call(
        "problem.testInput", user_id, db,
        kind="text", problemId=problem_id, testset=testset, testIndex=test_index,
    )


async def get_test_answer(
    problem_id: int, testset: str, test_index: int, user_id: int, db: AsyncSession
) -> str:
    """``problem.testAnswer`` -> the jury answer for the test."""
    return await call(
        "problem.testAnswer", user_id, db,
        kind="text", problemId=problem_id, testset=testset, testIndex=test_index,
    )


async def save_test(
    problem_id: int,
    testset: str,
    test_index: int,
    test_input: bytes | str | None,
    user_id: int,
    db: AsyncSession,
    *,
    check_existing: bool | None = None,
    test_group: str | None = None,
    test_points: float | None = None,
    test_description: str | None = None,
    test_use_in_statements: bool | None = None,
    test_input_for_statements: str | None = None,
    test_output_for_statements: str | None = None,
    verify_input_output_for_statements: bool | None = None,
) -> None:
    """``problem.saveTest``.

    ``test_input=None`` edits only the metadata of an existing test (group,
    points, ...), so a script-generated test keeps its input. The input is
    signed as text (UTF-8 ``bytes`` are decoded by the core).
    """
    method = "problem.saveTest"
    if test_points is not None and not (0 <= test_points < 1e9):
        raise PolygonParamError("testPoints: от 0 до 10^9", method=method)
    await call(
        method, user_id, db,
        problemId=problem_id,
        testset=testset,
        testIndex=test_index,
        testInput=test_input,
        checkExisting=check_existing,
        testGroup=test_group,
        testPoints=None if test_points is None else round(float(test_points), 2),
        testDescription=test_description,
        testUseInStatements=test_use_in_statements,
        testInputForStatements=test_input_for_statements,
        testOutputForStatements=test_output_for_statements,
        verifyInputOutputForStatements=verify_input_output_for_statements,
    )


async def delete_tests(
    problem_id: int,
    testset: str,
    test_indices: Iterable[int],
    user_id: int,
    db: AsyncSession,
) -> None:
    """``problem.deleteTest``.

    Polygon pre-checks every test and deletes nothing if one fails; the
    details (``DeleteTestsResult.failures``) are in ``PolygonAPIError.result``.
    """
    method = "problem.deleteTest"
    await call(
        method, user_id, db,
        problemId=problem_id, testset=testset, testIndices=_indices(method, test_indices),
    )


async def set_test_group(
    problem_id: int,
    testset: str,
    test_group: str,
    test_indices: Iterable[int],
    user_id: int,
    db: AsyncSession,
) -> None:
    """``problem.setTestGroup`` -- move tests into a group (groups must be enabled)."""
    method = "problem.setTestGroup"
    await call(
        method, user_id, db,
        problemId=problem_id,
        testset=testset,
        testGroup=test_group,
        testIndices=_indices(method, test_indices),
    )
