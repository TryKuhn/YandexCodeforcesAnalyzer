"""Upload manual sample tests (the statement examples) to Polygon.

Samples are saved as manual tests with ``testUseInStatements=True`` so they show
up as examples in the statement. They are idempotent (same index overwrites), so
re-running a build does not duplicate them.
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.files.test.post.save_test import save_test

logger = logging.getLogger(__name__)


async def upload_examples(
    db: AsyncSession,
    problem_id: int,
    user_id: int,
    examples: list,
    *,
    group: str | None = None,
) -> int:
    """Save examples as manual sample tests (indices 1..N). Returns count saved."""
    saved = 0
    for i, ex in enumerate(examples, start=1):
        inp = (ex or {}).get("input", "")
        if not str(inp).strip():
            continue
        try:
            await save_test(
                problem_id=problem_id,
                testset="tests",
                test_index=i,
                test_input=inp,
                test_use_in_statements=True,
                test_group=group,
                user_id=user_id,
                db=db,
            )
            saved += 1
        except Exception as e:
            logger.warning(f"Failed to upload sample test {i}: {e}")
    return saved
