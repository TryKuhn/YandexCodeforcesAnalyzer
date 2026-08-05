"""Contest CRUD and standings."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt.jwt_token import get_current_user
from app.database import get_db
from models.judge.contest import (JudgeContest, JudgeContestParticipant,
                                  JudgeContestProblem, ScoringKind)
from models.judge.submission import JudgeSubmission
from models.user.role import Role
from models.user.user import User

from .cache import ScoreboardCache
from .scoreboard import SubmissionFact, build_rows, places

contest_router = APIRouter()

# no backend yet means no cache; the board is simply recomputed every time
_cache = ScoreboardCache(backend=None)


def set_cache_backend(backend) -> None:
    """Wire a Redis client in at startup."""
    global _cache
    _cache = ScoreboardCache(backend=backend)


async def require_admin(
    user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> int:
    """Only Admin may shape contests; everyone may look at them."""
    result = await db.execute(
        select(Role.name).join(User, User.role_id == Role.id).where(User.id == user_id)
    )
    role = result.scalar_one_or_none()
    if role != "Admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required"
        )
    return user_id


class ProblemSlot(BaseModel):
    problem_id: int
    position: int
    max_points: float = 100.0


class ContestIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    scoring: str = ScoringKind.ICPC.value
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    freeze_minutes: int | None = None
    problems: list[ProblemSlot] = Field(default_factory=list)


def _contest_payload(contest: JudgeContest) -> dict:
    return {
        "id": contest.id,
        "name": contest.name,
        "scoring": contest.scoring,
        "starts_at": contest.starts_at,
        "ends_at": contest.ends_at,
        "freeze_minutes": contest.freeze_minutes,
        "problems": [
            {
                "letter": slot.letter,
                "position": slot.position,
                "problem_id": slot.problem_id,
                "max_points": slot.max_points,
            }
            for slot in contest.problems
        ],
    }


async def _get_contest(db: AsyncSession, contest_id: int) -> JudgeContest:
    contest = await db.get(JudgeContest, contest_id)
    if contest is None:
        raise HTTPException(status_code=404, detail="contest not found")
    return contest


@contest_router.get("")
async def list_contests(db: AsyncSession = Depends(get_db)) -> list[dict]:
    result = await db.execute(select(JudgeContest).order_by(JudgeContest.starts_at.desc()))
    return [_contest_payload(c) for c in result.scalars().all()]


@contest_router.get("/{contest_id}")
async def get_contest(contest_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    return _contest_payload(await _get_contest(db, contest_id))


@contest_router.post("", status_code=201)
async def create_contest(
    body: ContestIn,
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_admin),
) -> dict:
    if body.scoring not in {kind.value for kind in ScoringKind}:
        raise HTTPException(status_code=422, detail=f"unknown scoring: {body.scoring}")

    contest = JudgeContest(
        name=body.name,
        scoring=body.scoring,
        ends_at=body.ends_at,
        freeze_minutes=body.freeze_minutes,
        problems=[
            JudgeContestProblem(
                problem_id=slot.problem_id,
                position=slot.position,
                max_points=slot.max_points,
            )
            for slot in body.problems
        ],
    )
    if body.starts_at is not None:
        contest.starts_at = body.starts_at
    db.add(contest)
    await db.commit()
    await db.refresh(contest)
    return _contest_payload(contest)


@contest_router.put("/{contest_id}")
async def update_contest(
    contest_id: int,
    body: ContestIn,
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_admin),
) -> dict:
    contest = await _get_contest(db, contest_id)
    contest.name = body.name
    contest.scoring = body.scoring
    contest.ends_at = body.ends_at
    contest.freeze_minutes = body.freeze_minutes
    if body.starts_at is not None:
        contest.starts_at = body.starts_at

    contest.problems.clear()
    for slot in body.problems:
        contest.problems.append(
            JudgeContestProblem(
                problem_id=slot.problem_id,
                position=slot.position,
                max_points=slot.max_points,
            )
        )
    await db.commit()
    await db.refresh(contest)
    # the board depends on which problems are in the contest
    await _cache.invalidate(contest_id)
    return _contest_payload(contest)


@contest_router.delete("/{contest_id}", status_code=204)
async def delete_contest(
    contest_id: int,
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_admin),
) -> None:
    contest = await _get_contest(db, contest_id)
    await db.delete(contest)
    await db.commit()
    await _cache.invalidate(contest_id)


@contest_router.post("/{contest_id}/participants", status_code=201)
async def register_participant(
    contest_id: int,
    user_id: int,
    display_name: str,
    is_official: bool = True,
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_admin),
) -> dict:
    await _get_contest(db, contest_id)
    participant = JudgeContestParticipant(
        contest_id=contest_id,
        user_id=user_id,
        display_name=display_name,
        is_official=is_official,
    )
    db.add(participant)
    await db.commit()
    await _cache.invalidate(contest_id)
    return {"id": participant.id, "user_id": user_id, "display_name": display_name}


@contest_router.get("/{contest_id}/scoreboard")
async def scoreboard(contest_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    cached = await _cache.read(contest_id)
    if cached is not None:
        return cached

    contest = await _get_contest(db, contest_id)
    problem_ids = [slot.problem_id for slot in contest.problems]

    people = (
        await db.execute(
            select(JudgeContestParticipant).where(
                JudgeContestParticipant.contest_id == contest_id
            )
        )
    ).scalars().all()
    participants = {p.user_id: (p.display_name, p.is_official) for p in people}

    facts: list[SubmissionFact] = []
    if problem_ids and participants:
        rows = (
            await db.execute(
                select(JudgeSubmission).where(
                    JudgeSubmission.contest_id == contest_id,
                    JudgeSubmission.status == "judged",
                )
            )
        ).scalars().all()
        for submission in rows:
            minute = max(0, int((submission.created_at - contest.starts_at).total_seconds() // 60))
            facts.append(
                SubmissionFact(
                    user_id=submission.user_id or 0,
                    problem_id=submission.problem_id,
                    verdict=submission.verdict or "",
                    score=submission.score or 0.0,
                    minute=minute,
                )
            )

    ranked = build_rows(facts, participants, contest.scoring)
    payload = {
        "contest_id": contest_id,
        "scoring": contest.scoring,
        "problems": [
            {"letter": slot.letter, "problem_id": slot.problem_id}
            for slot in contest.problems
        ],
        "rows": [
            {
                "place": place,
                "user_id": row.user_id,
                "display_name": row.display_name,
                "is_official": row.is_official,
                "solved": row.solved,
                "penalty": row.penalty,
                "score": row.score,
                "cells": [
                    {
                        "problem_id": cell.problem_id,
                        "solved": cell.solved,
                        "attempts": cell.attempts,
                        "score": cell.score,
                        "solved_at": cell.solved_at,
                    }
                    for cell in row.cells.values()
                ],
            }
            for row, place in zip(ranked, places(ranked, contest.scoring))
        ],
    }
    await _cache.write(contest_id, payload)
    return payload


async def on_submission_judged(contest_id: int | None) -> None:
    """Drop the cached board so the next reader sees the new result."""
    if contest_id is not None:
        await _cache.invalidate(contest_id)
