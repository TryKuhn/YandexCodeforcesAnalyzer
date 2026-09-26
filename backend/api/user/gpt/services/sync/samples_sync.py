"""Upload manual sample tests (the statement examples) to Polygon.

Samples are saved as manual tests with ``testUseInStatements=True`` so they show
up as examples in the statement. They are idempotent (same index overwrites), so
re-running a build does not duplicate them.
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.files.test.post.delete_tests import delete_tests
from api.user.polygon.files.test.post.save_test import save_test

logger = logging.getLogger(__name__)


def unique_examples(examples: list) -> list:
    """Drop examples with an empty or repeated input.

    Polygon rejects two identical manual tests ('Test coincides with test
    #...'); inputs differing only in whitespace count as identical.
    """
    seen: set[str] = set()
    unique: list[dict] = []
    for ex in examples:
        inp = str((ex or {}).get("input", ""))
        key = " ".join(inp.split())  # normalise whitespace for comparison
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(ex)
    return unique


async def upload_examples(
    db: AsyncSession,
    problem_id: int,
    user_id: int,
    examples: list,
    *,
    group: str | None = None,
) -> int:
    """Save examples as manual sample tests (indices 1..N). Returns count saved.

    Duplicate / empty inputs are dropped first (see unique_examples) and the
    rest are re-indexed sequentially before upload.
    """
    saved = 0
    for i, ex in enumerate(unique_examples(examples), start=1):
        try:
            await save_test(
                problem_id=problem_id,
                testset="tests",
                test_index=i,
                test_input=ex.get("input", ""),
                test_use_in_statements=True,
                test_group=group,
                user_id=user_id,
                db=db,
            )
            saved += 1
        except Exception as e:
            logger.warning(f"Failed to upload sample test {i}: {e}")
    return saved


async def delete_stale_examples(
    db: AsyncSession, problem_id: int, user_id: int, fresh: int, stale: int,
) -> bool:
    """Delete old sample tests ``fresh+1..stale`` the new samples did not overwrite.

    New samples replace old ones index by index, so when there are fewer of them
    the tail of the old ones would stay and fail the new validator. Returns
    False if Polygon refused (it then deletes nothing, e.g. when one of those
    indices is a script-generated test, not an old sample).
    """
    if fresh >= stale:
        return True
    try:
        await delete_tests(problem_id, "tests", list(range(fresh + 1, stale + 1)),
                           user_id, db)
    except Exception as e:
        logger.warning(f"Failed to delete stale sample tests {fresh + 1}..{stale}: {e}")
        return False
    return True
