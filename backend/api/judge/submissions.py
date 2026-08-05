"""Submitting a solution and looking at your own attempts."""
from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt.jwt_token import get_current_user
from app.database import get_db
from blobs import BlobStore
from models.judge.contest import (JudgeContest, JudgeContestParticipant,
                                  JudgeContestProblem)
from models.judge.submission import JudgeSubmission

from .contests import contest_router
from .grading import JOB_TYPE

# a solution longer than this is not a solution
MAX_SOURCE_BYTES = 256 * 1024
SUPPORTED_LANGUAGES = {"cpp", "python"}

_store = BlobStore()
# set at startup; without a queue the submission is stored but never judged
_enqueue = None


def set_enqueue(enqueue) -> None:
    global _enqueue
    _enqueue = enqueue


class SubmissionIn(BaseModel):
    problem_id: int
    language: str = "cpp"
    source: str = Field(min_length=1)


def _payload(submission: JudgeSubmission) -> dict:
    return {
        "id": submission.id,
        "problem_id": submission.problem_id,
        "language": submission.language,
        "status": submission.status,
        "verdict": submission.verdict,
        "score": submission.score,
        "max_time_ms": submission.max_time_ms,
        "max_memory_kb": submission.max_memory_kb,
        "first_failed_test": submission.first_failed_test,
        "created_at": submission.created_at,
        "judged_at": submission.judged_at,
    }


async def _require_participant(
    db: AsyncSession, contest_id: int, user_id: int
) -> JudgeContest:
    contest = await db.get(JudgeContest, contest_id)
    if contest is None:
        raise HTTPException(status_code=404, detail="contest not found")

    registered = await db.scalar(
        select(JudgeContestParticipant.id).where(
            JudgeContestParticipant.contest_id == contest_id,
            JudgeContestParticipant.user_id == user_id,
        )
    )
    if registered is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="you are not registered for this contest",
        )
    return contest


@contest_router.post("/{contest_id}/submissions", status_code=201)
async def submit(
    contest_id: int,
    body: SubmissionIn,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user),
) -> dict:
    """Accept a solution, store it, and queue it for judging."""
    await _require_participant(db, contest_id, user_id)

    if body.language not in SUPPORTED_LANGUAGES:
        raise HTTPException(status_code=422, detail=f"unsupported language: {body.language}")

    source = body.source.encode()
    if len(source) > MAX_SOURCE_BYTES:
        raise HTTPException(status_code=413, detail="source is too large")

    in_contest = await db.scalar(
        select(JudgeContestProblem.id).where(
            JudgeContestProblem.contest_id == contest_id,
            JudgeContestProblem.problem_id == body.problem_id,
        )
    )
    if in_contest is None:
        raise HTTPException(status_code=404, detail="problem is not in this contest")

    # the source goes to the blob store, so identical submissions cost nothing
    source_sha = await _store.put(db, source)
    submission = JudgeSubmission(
        problem_id=body.problem_id,
        contest_id=contest_id,
        user_id=user_id,
        language=body.language,
        source_sha=source_sha,
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    if _enqueue is not None:
        await _enqueue(db, JOB_TYPE, {"submission_id": submission.id}, user_id=user_id)

    return _payload(submission)


@contest_router.get("/{contest_id}/submissions/my")
async def my_submissions(
    contest_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user),
) -> list[dict]:
    """Own attempts only; other contestants' code stays private."""
    await _require_participant(db, contest_id, user_id)

    rows = (
        await db.execute(
            select(JudgeSubmission)
            .where(
                JudgeSubmission.contest_id == contest_id,
                JudgeSubmission.user_id == user_id,
            )
            .order_by(JudgeSubmission.created_at.desc())
        )
    ).scalars().all()
    return [_payload(row) for row in rows]
