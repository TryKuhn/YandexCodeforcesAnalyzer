"""Fetch the input for a test of a Polygon problem."""
import base64

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import get_user, polygon_call


async def get_test_input(
    problem_id: int, testset: str, test_index: int, user_id: int, db: AsyncSession
) -> str:
    """Return a test's input, via ``problem.tests``.

    NOT ``problem.testInput``: that method serves only GENERATED tests and
    returns plain text (not JSON), so it fails for MANUAL sample tests — which is
    exactly what the statement examples are. ``problem.tests`` carries the input
    for manual tests in ``input`` (or ``inputBase64``).
    """
    user = await get_user(user_id, db)
    tests = await polygon_call(
        "problem.tests", {"problemId": str(problem_id), "testset": testset}, user
    )
    if isinstance(tests, list):
        for t in tests:
            if isinstance(t, dict) and str(t.get("index")) == str(test_index):
                if t.get("input") is not None:
                    return t["input"]
                if t.get("inputBase64"):
                    return base64.b64decode(t["inputBase64"]).decode("utf-8", "replace")
                return ""
    return ""
