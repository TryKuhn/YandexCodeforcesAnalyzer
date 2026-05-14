import asyncio
import logging
from base64 import b64decode
from concurrent.futures import ThreadPoolExecutor
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
from models.contest.contest_participant import ContestParticipant
from models.plagiarism.pair_of_banned_submissions import \
    PairOfBannedSubmissions
from models.plagiarism.plagiarism_report import PlagiarismReport

router = APIRouter()
logger = logging.getLogger(__name__)
_plagiarism_executor = ThreadPoolExecutor(max_workers=2)


def _run_plagiarism_check(sub_rows: list, threshold: float) -> list:
    py_submissions = []
    for sub in sub_rows:
        py_sub = plagiarism_cpp.Submission()
        py_sub.id = str(sub["id"])
        py_sub.language = plagiarism_cpp.ProgrammingLanguage.Cpp
        py_sub.rawCode = b64decode(sub["source"]).decode("utf-8")
        py_sub.participant = sub["participant"] or ""
        py_sub.problem = sub["task_name"] or ""
        py_submissions.append(py_sub)
    return plagiarism_cpp.compute_similarity_pairs(py_submissions, threshold)


class PlagiarismCheckBody(BaseModel):
    threshold: float
    onlyOk: bool = False
    languages: list[str] | None = None
    tasks: list[str] | None = None


@router.get("/contests/{contest_id}/reports")
async def get_contest_reports(
    contest_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _contest_q = await db.execute(
        select(Contest).filter_by(id=contest_id, user_id=user_id)
    )
    contest = _contest_q.scalars().first()

    if not contest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found"
        )

    _reports_q = await db.execute(
        select(PlagiarismReport)
        .filter_by(contest_id=contest_id)
        .order_by(PlagiarismReport.id.desc())
    )
    reports = _reports_q.scalars().all()

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


@router.get("/contests/{contest_id}/submissions/meta")
async def get_contest_submissions_meta(
    contest_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    contest = await db.execute(
        select(Contest).filter_by(id=contest_id, user_id=user_id)
    )
    if not contest.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found")

    languages_result = await db.execute(
        select(Submission.language).distinct().filter_by(contest_id=contest_id)
    )
    tasks_result = await db.execute(
        select(Submission.task_name).distinct().filter_by(contest_id=contest_id)
    )

    return {
        "languages": sorted(lang for lang in languages_result.scalars().all() if lang),
        "tasks": sorted(task for task in tasks_result.scalars().all() if task),
    }


@router.get("/reports/{report_id}")
async def get_report(
    report_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=10, le=100),
    task_name: str = Query(None),
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _report_q = await db.execute(select(PlagiarismReport).filter_by(id=report_id))
    report = _report_q.scalars().first()

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Report not found"
        )

    _contest_q = await db.execute(
        select(Contest).filter_by(id=report.contest_id, user_id=user_id)
    )
    contest = _contest_q.scalars().first()

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

    tasks_query = (
        select(Submission.task_name)
        .distinct()
        .join(
            PairOfBannedSubmissions,
            PairOfBannedSubmissions.first_submission_id == Submission.id,
        )
        .filter(PairOfBannedSubmissions.report_id == report_id)
    )
    _tasks_q = await db.execute(tasks_query)
    available_tasks = [t for t in _tasks_q.scalars().all() if t]

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
    _total_q = await db.execute(total_query)
    total = _total_q.scalar() or 0

    pairs_result = await db.execute(
        query.order_by(PairOfBannedSubmissions.percentage.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    pairs = pairs_result.scalars().all()

    # Batch-load participant names for this page of pairs
    logins = set()
    for pair in pairs:
        logins.add(pair.first_submission.participant_login)
        logins.add(pair.second_submission.participant_login)

    name_map: dict[str, str | None] = {}
    if logins:
        cp_result = await db.execute(
            select(ContestParticipant).filter(
                ContestParticipant.contest_id == report.contest_id,
                ContestParticipant.login.in_(logins),
            )
        )
        for cp in cp_result.scalars().all():
            name_map[cp.login] = cp.name

    return {
        "id": report.id,
        "status": report.status,
        "tasks": available_tasks,
        "pairs": [
            {
                "id": pair.id,
                "user1": pair.first_submission.participant_login,
                "user1_name": name_map.get(pair.first_submission.participant_login),
                "user2": pair.second_submission.participant_login,
                "user2_name": name_map.get(pair.second_submission.participant_login),
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
    _pair_q = await db.execute(
        select(PairOfBannedSubmissions)
        .options(
            joinedload(PairOfBannedSubmissions.first_submission),
            joinedload(PairOfBannedSubmissions.second_submission),
        )
        .filter_by(id=pair_id)
    )
    pair = _pair_q.scalars().first()

    if not pair:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pair not found"
        )

    _contest_q = await db.execute(
        select(Contest).filter_by(id=pair.contest_id, user_id=user_id)
    )
    contest = _contest_q.scalars().first()

    if not contest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found"
        )

    login1 = pair.first_submission.participant_login
    login2 = pair.second_submission.participant_login

    cp_result = await db.execute(
        select(ContestParticipant).filter(
            ContestParticipant.contest_id == pair.contest_id,
            ContestParticipant.login.in_([login1, login2]),
        )
    )
    name_map = {cp.login: cp.name for cp in cp_result.scalars().all()}

    return {
        "id": pair.id,
        "percent": round(pair.percentage, 2),
        "user1": login1,
        "user1_name": name_map.get(login1),
        "user2": login2,
        "user2_name": name_map.get(login2),
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
    _contest_q = await db.execute(
        select(Contest).filter_by(id=contest_id, user_id=user_id)
    )
    contest = _contest_q.scalars().first()

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

    logger.info(
        f"Plagiarism check started: report_id={report.id} contest_id={contest_id} "
        f"threshold={body.threshold} only_ok={body.onlyOk} "
        f"languages={body.languages} tasks={body.tasks} user_id={user_id}"
    )

    asyncio.create_task(
        process_plagiarism_report(
            report_id=report.id,
            contest_id=contest_id,
            threshold=body.threshold,
            only_ok=body.onlyOk,
            languages=body.languages,
            tasks=body.tasks,
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
    languages: list[str] | None = None,
    tasks: list[str] | None = None,
):
    async with Session() as db:
        try:
            query = select(Submission).filter_by(contest_id=contest_id)

            if only_ok:
                query = query.filter_by(verdict="OK")

            if languages:
                query = query.filter(Submission.language.in_(languages))

            if tasks:
                query = query.filter(Submission.task_name.in_(tasks))

            submissions_result = await db.execute(query)
            submissions = submissions_result.scalars().all()

            # Extract plain dicts — SQLAlchemy objects must not be passed across threads
            sub_rows = [
                {
                    "id": s.id,
                    "source": s.source,
                    "participant": s.participant_login,
                    "task_name": s.task_name,
                }
                for s in submissions
                if s.source
            ]

            logger.info(
                f"[report={report_id}] Comparing {len(sub_rows)} submissions "
                f"(contest={contest_id}, threshold={threshold})"
            )

            # Run ALL CPU-bound work (data prep + similarity computation) in a
            # dedicated thread pool so the event loop stays free for other requests.
            loop = asyncio.get_running_loop()
            pairs = await loop.run_in_executor(
                _plagiarism_executor,
                _run_plagiarism_check,
                sub_rows,
                threshold,
            )

            logger.info(f"[report={report_id}] Found {len(pairs)} suspicious pairs")

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
            logger.info(f"[report={report_id}] Plagiarism check completed")

        except Exception:
            logger.exception(f"[report={report_id}] Plagiarism check failed")
            report = await db.get(PlagiarismReport, report_id)
            if report:
                report.status = "failed"
                await db.commit()
            raise
