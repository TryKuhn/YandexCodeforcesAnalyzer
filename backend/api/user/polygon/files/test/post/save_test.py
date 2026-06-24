"""Save or update a test of a Polygon problem testset."""

from typing import Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def save_test(
    problem_id: int,
    testset: str,
    test_index: int,
    test_input: Optional[Union[bytes, str]],
    user_id: int,
    db: AsyncSession,
    check_existing: Optional[bool] = None,
    test_group: Optional[str] = None,
    test_points: Optional[float] = None,
    test_description: Optional[str] = None,
    test_use_in_statements: Optional[bool] = None,
    test_input_for_statements: Optional[str] = None,
    test_output_for_statements: Optional[str] = None,
    verify_input_output_for_statements: Optional[bool] = None,
):
    """Save / update a test. ``test_input`` can be bytes or str; pass ``None`` to
    update only metadata (points/group/…) of an EXISTING test by index — Polygon
    treats ``testInput`` as optional, so a script-generated test keeps its input.

    ``testInput`` is sent as a TEXT param (like ``source``/``file`` in
    saveScript/saveSolution) so it is INCLUDED in the API signature. Sending it
    as bytes would make ``polygon_call`` treat it as an excluded binary param,
    and Polygon then rejects the request with 'apiKey: Incorrect signature'.
    """
    if isinstance(test_input, bytes):
        test_input = test_input.decode("utf-8", errors="replace")

    user = await get_user(user_id, db)
    params: dict = {
        "problemId": str(problem_id),
        "testset": testset,
        "testIndex": str(test_index),
    }
    if test_input is not None:
        params["testInput"] = test_input

    if check_existing is not None:
        params["checkExisting"] = "true" if check_existing else "false"
    if test_group:
        params["testGroup"] = test_group
    if test_points is not None:
        params["testPoints"] = str(test_points)
    if test_description:
        params["testDescription"] = test_description
    if test_use_in_statements is not None:
        params["testUseInStatements"] = "true" if test_use_in_statements else "false"
    if test_input_for_statements:
        params["testInputForStatements"] = test_input_for_statements
    if test_output_for_statements:
        params["testOutputForStatements"] = test_output_for_statements
    if verify_input_output_for_statements is not None:
        params["verifyInputOutputForStatements"] = (
            "true" if verify_input_output_for_statements else "false"
        )

    return await polygon_call("problem.saveTest", params, user)
