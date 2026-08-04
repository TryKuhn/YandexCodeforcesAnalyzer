"""The job that turns a queued submission into a verdict."""
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from blobs import BlobStore
from models.base import utcnow
from models.judge.problem import JudgeProblem
from models.judge.run import JudgeRun
from models.judge.submission import JudgeSubmission
from models.judge.test import JudgeTest

from .client import JudgeTestPayload, JudgeUnavailable, judge_submission
from .contests import on_submission_judged

logger = logging.getLogger(__name__)

JOB_TYPE = "judge.submission"

_STATUS_JUDGED = "judged"
_STATUS_RUNNING = "running"


async def grade(db: AsyncSession, store: BlobStore, submission_id: int) -> dict:
    """Fetch everything the judge needs, run it, store the outcome."""
    submission = await db.get(JudgeSubmission, submission_id)
    if submission is None:
        raise ValueError(f"submission {submission_id} is gone")

    problem = await db.get(JudgeProblem, submission.problem_id)
    if problem is None:
        raise ValueError(f"problem {submission.problem_id} is gone")
    if not problem.checker_sha:
        raise ValueError(f"problem {problem.id} has no checker")

    tests = (
        await db.execute(
            select(JudgeTest)
            .where(JudgeTest.problem_id == problem.id)
            .order_by(JudgeTest.index)
        )
    ).scalars().all()
    if not tests:
        raise ValueError(f"problem {problem.id} has no tests")
    if any(test.answer_sha is None for test in tests):
        raise ValueError(f"problem {problem.id} has tests without jury answers")

    submission.status = _STATUS_RUNNING
    await db.commit()

    payload = await judge_submission(
        source=await store.get(submission.source_sha),
        language=submission.language,
        checker=await store.get(problem.checker_sha),
        tests=[
            JudgeTestPayload(
                index=test.index,
                input_data=await store.get(test.input_sha),
                answer_data=await store.get(test.answer_sha or ""),
                points=test.points or 0.0,
                group=test.group_name,
            )
            for test in tests
        ],
        time_limit_ms=problem.time_limit_ms,
        memory_limit_mb=problem.memory_limit_mb,
    )

    await _store_outcome(db, store, submission, payload)
    # the board must not keep showing a stale result
    await on_submission_judged(submission.contest_id)
    return {"submission_id": submission.id, "verdict": submission.verdict}


async def _store_outcome(
    db: AsyncSession, store: BlobStore, submission: JudgeSubmission, payload: dict
) -> None:
    submission.verdict = payload["verdict"]
    submission.score = payload.get("score", 0.0)
    submission.max_time_ms = payload.get("max_time_ms")
    submission.max_memory_kb = payload.get("max_memory_kb")
    submission.first_failed_test = payload.get("first_failed_test")
    submission.status = _STATUS_JUDGED
    submission.judged_at = utcnow()

    log = payload.get("compile_log") or ""
    if log:
        submission.compile_log_sha = await store.put(db, log.encode())

    for entry in payload.get("tests", []):
        db.add(
            JudgeRun(
                submission_id=submission.id,
                test_index=entry["index"],
                verdict=entry["verdict"],
                time_ms=entry.get("time_ms", 0),
                memory_kb=entry.get("memory_kb", 0),
                checker_comment=(entry.get("comment") or None),
            )
        )
    await db.commit()


def make_handler(
    session_factory, store: BlobStore
) -> Callable[[dict, Callable[[int], Awaitable[None]]], Awaitable[dict]]:
    """Build the worker handler; the worker owns retries, we only do the work."""

    async def handler(payload: dict, progress) -> dict:
        submission_id = int(payload["submission_id"])
        async with session_factory() as db:
            await progress(10)
            try:
                result = await grade(db, store, submission_id)
            except JudgeUnavailable:
                # let the worker retry: the submission is fine, the judge is not
                raise
            await progress(100)
            return result

    return handler
