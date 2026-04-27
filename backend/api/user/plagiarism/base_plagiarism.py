import asyncio
from base64 import b64decode
from math import ceil

import plagiarism_cpp
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from api.crypt import get_current_user
from app.database import Session, get_db
from models import Contest, Submission
from models.plagiarism.pair_of_banned_submissions import \
    PairOfBannedSubmissions
from models.plagiarism.plagiarism_report import PlagiarismReport

router = APIRouter()


class PlagiarismCheckBody(BaseModel):
    threshold: float
    onlyOk: bool = False


@router.get("/contests/{contest_id}/reports")
async def get_contest_reports(
    contest_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    contest = await db.execute(
        select(Contest).filter_by(id=contest_id, user_id=user_id)
    )
    contest = contest.scalars().first()

    if not contest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found"
        )

    reports = await db.execute(
        select(PlagiarismReport)
        .filter_by(contest_id=contest_id)
        .order_by(PlagiarismReport.id.desc())
    )
    reports = reports.scalars().all()

    return [
        {
            "id": report.id,
            "contest_id": report.contest_id,
            "status": report.status,
            "threshold": report.threshold,
            "only_ok": report.only_ok,
            "created_at": report.created_at,
            "pairs_count": len(report.pairs),
        }
        for report in reports
    ]


@router.get("/reports/{report_id}")
async def get_report(
    report_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=10, le=100),
    task_name: str = Query(None),
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    report = await db.execute(select(PlagiarismReport).filter_by(id=report_id))
    report = report.scalars().first()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )

    contest = await db.execute(
        select(Contest).filter_by(id=report.contest_id, user_id=user_id)
    )
    contest = contest.scalars().first()

    if not contest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found"
        )

    if report.status != "completed":
        return {
            "id": report.id,
            "contest_id": report.contest_id,
            "status": report.status,
            "pairs": [],
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": 0,
                "total_pages": 1,
            },
        }

    tasks = (
        select(Submission.task_name)
        .distinct()
        .join(
            PairOfBannedSubmissions,
            PairOfBannedSubmissions.first_submission_id == Submission.id,
        )
        .filter(PairOfBannedSubmissions.report_id == report_id)
    )
    tasks = await db.execute(tasks)
    available_tasks = [t for t in tasks.scalars().all() if t]

    query = (
        select(PairOfBannedSubmissions)
        .options(
            joinedload(PairOfBannedSubmissions.first_submission),
            joinedload(PairOfBannedSubmissions.second_submission),
        )
        .filter_by(report_id=report_id)
    )

    if task_name:
        query = query.join(
            Submission, PairOfBannedSubmissions.first_submission_id == Submission.id
        ).filter(Submission.task_name == task_name)

    total_query = select(func.count()).select_from(query.subquery())
    total = await db.execute(total_query)
    total = total.scalar() or 0

    pairs_result = await db.execute(
        query.order_by(PairOfBannedSubmissions.percentage.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    pairs = pairs_result.scalars().all()

    return {
        "id": report.id,
        "status": report.status,
        "tasks": available_tasks,
        "pairs": [
            {
                "id": pair.id,
                "user1": pair.first_submission.participant_login,
                "user2": pair.second_submission.participant_login,
                "task_name": pair.first_submission.task_name,
                "percent": round(pair.percentage, 2),
            }
            for pair in pairs
        ],
        "pagination": {
            "page": page,
            "total": total,
            "total_pages": ceil(total / per_page) if total > 0 else 1,
        },
    }


@router.get("/pairs/{pair_id}")
async def get_pair(
    pair_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pair = await db.execute(
        select(PairOfBannedSubmissions)
        .options(
            joinedload(PairOfBannedSubmissions.first_submission),
            joinedload(PairOfBannedSubmissions.second_submission),
        )
        .filter_by(id=pair_id)
    )
    pair = pair.scalars().first()

    if not pair:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pair not found"
        )

    contest = await db.execute(
        select(Contest).filter_by(id=pair.contest_id, user_id=user_id)
    )
    contest = contest.scalars().first()

    if not contest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found"
        )

    return {
        "id": pair.id,
        "percent": round(pair.percentage, 2),
        "user1": pair.first_submission.participant_login,
        "user2": pair.second_submission.participant_login,
        "sub1_id": str(pair.first_submission_id),
        "sub2_id": str(pair.second_submission_id),
        "code1": pair.first_submission.source or "",
        "code2": pair.second_submission.source or "",
    }


@router.post("/contests/{contest_id}/check")
async def run_plagiarism_check(
    contest_id: int,
    body: PlagiarismCheckBody,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    contest = await db.execute(
        select(Contest).filter_by(id=contest_id, user_id=user_id)
    )
    contest = contest.scalars().first()

    if not contest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found"
        )

    report = PlagiarismReport(
        contest_id=contest_id,
        status="processing",
        threshold=body.threshold,
        only_ok=body.onlyOk,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    asyncio.create_task(
        process_plagiarism_report(
            report_id=report.id,
            contest_id=contest_id,
            threshold=body.threshold,
            only_ok=body.onlyOk,
        )
    )

    return {
        "reportId": report.id,
        "status": "processing",
    }


async def process_plagiarism_report(
    report_id: int,
    contest_id: int,
    threshold: float,
    only_ok: bool,
):
    async with Session() as db:
        try:
            query = select(Submission).filter_by(contest_id=contest_id)

            if only_ok:
                query = query.filter_by(verdict="OK")

            submissions_result = await db.execute(query)
            submissions = submissions_result.scalars().all()

            py_submissions = []

            for submission in submissions:
                if not submission.source:
                    continue

                py_sub = plagiarism_cpp.Submission()
                py_sub.id = str(submission.id)
                py_sub.language = (
                    plagiarism_cpp.ProgrammingLanguage.Cpp
                )  # TODO: support more languages
                decoded_code = b64decode(submission.source).decode("utf-8")
                py_sub.rawCode = decoded_code
                py_sub.participant = submission.participant_login or ""
                py_sub.problem = submission.task_name or ""

                py_submissions.append(py_sub)

            pairs = plagiarism_cpp.compute_similarity_pairs(py_submissions, threshold)

            for pair in pairs:
                db.add(
                    PairOfBannedSubmissions(
                        contest_id=contest_id,
                        report_id=report_id,
                        first_submission_id=str(pair.first_submission_id),
                        second_submission_id=str(pair.second_submission_id),
                        percentage=pair.plagiarism_percent,
                    )
                )

            report = await db.get(PlagiarismReport, report_id)
            if report:
                report.status = "completed"

            await db.commit()

        except Exception:
            report = await db.get(PlagiarismReport, report_id)
            if report:
                report.status = "failed"
                await db.commit()
            raise
