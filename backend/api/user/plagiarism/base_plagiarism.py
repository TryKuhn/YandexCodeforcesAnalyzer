import asyncio
import logging
from base64 import b64decode
from concurrent.futures import ProcessPoolExecutor
from math import ceil

import plagiarism_cpp
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, selectinload

from api.crypt import get_current_user
from app.database import Session, get_db
from models import Contest, Submission
from models.contest.contest_participant import ContestParticipant
from models.contest.task_result import TaskResult
from models.plagiarism.pair_of_banned_submissions import \
    PairOfBannedSubmissions
from models.plagiarism.plagiarism_report import PlagiarismReport

router = APIRouter()
logger = logging.getLogger(__name__)
# ProcessPoolExecutor: each worker has its own GIL, so the main event loop
# is never blocked by the C++ plagiarism computation.
_plagiarism_executor = ProcessPoolExecutor(max_workers=4)


def _run_plagiarism_check(sub_rows: list, threshold: float) -> list[tuple]:
    """Runs in a subprocess. Returns plain tuples so the result is picklable."""
    py_submissions = []
    for sub in sub_rows:
        py_sub = plagiarism_cpp.Submission()
        py_sub.id = str(sub["id"])
        py_sub.language = plagiarism_cpp.ProgrammingLanguage.Cpp
        py_sub.rawCode = b64decode(sub["source"]).decode("utf-8")
        py_sub.participant = sub["participant"] or ""
        py_sub.problem = sub["task_name"] or ""
        py_submissions.append(py_sub)
    pairs = plagiarism_cpp.compute_similarity_pairs(py_submissions, threshold)
    return [
        (
            str(pair.first_submission_id),
            str(pair.second_submission_id),
            pair.plagiarism_percent,
        )
        for pair in pairs
    ]


class PlagiarismCheckBody(BaseModel):
    threshold: float  # display threshold (lower) — passed to C++ as the scan cutoff
    banThreshold: float  # auto-ban threshold (upper, >= threshold)
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
            "ban_threshold": report.ban_threshold,
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found"
        )

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
    search: str = Query(""),
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

    if search.strip():
        search_f = f"%{search.strip().lower()}%"
        matching_sub_ids = select(Submission.id).where(
            func.lower(Submission.participant_login).like(search_f)
        )
        query = query.filter(
            PairOfBannedSubmissions.first_submission_id.in_(matching_sub_ids)
            | PairOfBannedSubmissions.second_submission_id.in_(matching_sub_ids)
        )

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
        "sub1_banned": pair.first_submission.banned,
        "sub2_banned": pair.second_submission.banned,
    }


@router.post("/pairs/{pair_id}/ban/{position}")
async def ban_pair_submission(
    pair_id: int,
    position: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if position not in (1, 2):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Position must be 1 or 2"
        )

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
    if not _contest_q.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found"
        )

    sub_id = (
        str(pair.first_submission_id)
        if position == 1
        else str(pair.second_submission_id)
    )
    await _ban_task_result_for_submission(db, sub_id)
    await db.commit()

    return {"banned_submission_id": sub_id}


@router.post("/pairs/{pair_id}/unban/{position}")
async def unban_pair_submission(
    pair_id: int,
    position: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if position not in (1, 2):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Position must be 1 or 2"
        )

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
    if not _contest_q.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found"
        )

    sub_id = (
        str(pair.first_submission_id)
        if position == 1
        else str(pair.second_submission_id)
    )
    await _unban_task_result_for_submission(db, sub_id)
    await db.commit()

    return {"unbanned_submission_id": sub_id}


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
        ban_threshold=body.banThreshold,
        only_ok=body.onlyOk,
    )
    db.add(report)
    await db.commit()
    await db.refresh(report)

    logger.info(
        f"Plagiarism check started: report_id={report.id} contest_id={contest_id} "
        f"threshold={body.threshold} ban_threshold={body.banThreshold} "
        f"only_ok={body.onlyOk} languages={body.languages} tasks={body.tasks} user_id={user_id}"
    )

    asyncio.create_task(
        process_plagiarism_report(
            report_id=report.id,
            contest_id=contest_id,
            threshold=body.threshold,
            ban_threshold=body.banThreshold,
            only_ok=body.onlyOk,
            languages=body.languages,
            tasks=body.tasks,
        )
    )

    return {
        "reportId": report.id,
        "status": "processing",
    }


async def _unban_task_result_for_submission(db: AsyncSession, sub_id: str) -> None:
    """Reverse a ban: restore TaskResult score and unmark all submissions."""
    sub = await db.get(Submission, sub_id)
    if not sub:
        return

    tr_q = await db.execute(
        select(TaskResult)
        .options(selectinload(TaskResult.contest_participant))
        .filter_by(id=sub.task_result_id)
    )
    task_result = tr_q.scalars().first()
    if not task_result or not task_result.banned:
        return

    score_q = await db.execute(
        select(func.max(Submission.score)).where(
            Submission.task_result_id == task_result.id
        )
    )
    restored_score = score_q.scalar() or 0.0

    task_result.banned = False
    task_result.score = restored_score
    cp = task_result.contest_participant
    if cp:
        cp.score = (cp.score or 0.0) + restored_score

    await db.execute(
        update(Submission)
        .where(Submission.task_result_id == task_result.id)
        .values(banned=False)
    )


async def _ban_task_result_for_submission(db: AsyncSession, sub_id: str) -> None:
    """Ban the entire TaskResult (all submissions + zero score) for the given submission."""
    sub = await db.get(Submission, sub_id)
    if not sub:
        return

    tr_q = await db.execute(
        select(TaskResult)
        .options(selectinload(TaskResult.contest_participant))
        .filter_by(id=sub.task_result_id)
    )
    task_result = tr_q.scalars().first()
    if not task_result or task_result.banned:
        return

    task_result.banned = True
    cp = task_result.contest_participant
    if cp and task_result.score:
        cp.score = max(0.0, (cp.score or 0) - task_result.score)
    task_result.score = 0

    await db.execute(
        update(Submission)
        .where(Submission.task_result_id == task_result.id)
        .values(banned=True)
    )


async def process_plagiarism_report(
    report_id: int,
    contest_id: int,
    threshold: float,
    ban_threshold: float | None,
    only_ok: bool,
    languages: list[str] | None = None,
    tasks: list[str] | None = None,
):
    try:
        # ── 1. Load submissions, then release the DB connection ──────────────
        async with Session() as db:
            query = select(Submission).filter_by(contest_id=contest_id)
            if only_ok:
                query = query.filter_by(verdict="OK")
            if languages:
                query = query.filter(Submission.language.in_(languages))
            if tasks:
                query = query.filter(Submission.task_name.in_(tasks))

            submissions_result = await db.execute(query)
            submissions = submissions_result.scalars().all()

        # Keep only the last submission per (participant, task).
        # Sorting by id ascending ensures later IDs overwrite earlier ones.
        deduped: dict[tuple[str, str], dict] = {}
        for s in sorted(submissions, key=lambda x: x.send_time):
            if not s.source:
                continue
            key = (s.participant_login or "", s.task_name or "")
            deduped[key] = {
                "id": s.id,
                "source": s.source,
                "participant": s.participant_login,
                "task_name": s.task_name,
            }
        sub_rows = list(deduped.values())

        # Group by task so the C++ LSH runs per-task, not across all tasks.
        # Cross-task pairs are irrelevant and would bloat the candidate set O(n²).
        task_groups: dict[str, list[dict]] = {}
        for sub in sub_rows:
            task_groups.setdefault(sub["task_name"] or "", []).append(sub)

        logger.info(
            f"[report={report_id}] {len(sub_rows)} unique (participant, task) submissions "
            f"after dedup (raw={len(submissions)}) across {len(task_groups)} tasks "
            f"(contest={contest_id}, threshold={threshold})"
        )

        # ── 2. CPU-bound similarity computation, one task group per subprocess ─
        # Each task group is dispatched to the ProcessPoolExecutor independently,
        # so up to max_workers tasks run in parallel. asyncio.gather awaits all.
        loop = asyncio.get_running_loop()
        futures = [
            loop.run_in_executor(
                _plagiarism_executor,
                _run_plagiarism_check,
                group_subs,
                threshold,
            )
            for group_subs in task_groups.values()
            if len(group_subs) >= 2
        ]
        results = await asyncio.gather(*futures)
        pairs: list[tuple] = [p for task_pairs in results for p in task_pairs]

        logger.info(f"[report={report_id}] Found {len(pairs)} suspicious pairs")

        # ── 3. Persist results with a fresh DB connection ────────────────────
        async with Session() as db:
            for first_id, second_id, percent in pairs:
                db.add(
                    PairOfBannedSubmissions(
                        contest_id=contest_id,
                        report_id=report_id,
                        first_submission_id=first_id,
                        second_submission_id=second_id,
                        percentage=percent,
                    )
                )

            report = await db.get(PlagiarismReport, report_id)
            if report:
                report.status = "completed"

            await db.commit()

        # ── 4. Auto-ban pairs above ban_threshold ────────────────────────────
        if ban_threshold is not None:
            ban_pairs = [
                (fid, sid) for fid, sid, pct in pairs if pct >= ban_threshold * 100
            ]
            if ban_pairs:
                async with Session() as db:
                    banned_ids: set[str] = set()
                    for first_id, second_id in ban_pairs:
                        if first_id not in banned_ids:
                            await _ban_task_result_for_submission(db, first_id)
                            banned_ids.add(first_id)
                        if second_id not in banned_ids:
                            await _ban_task_result_for_submission(db, second_id)
                            banned_ids.add(second_id)
                    await db.commit()
                logger.info(
                    f"[report={report_id}] Auto-banned {len(banned_ids)} submissions "
                    f"(ban_threshold={ban_threshold})"
                )

        logger.info(f"[report={report_id}] Plagiarism check completed")

    except Exception:
        logger.exception(f"[report={report_id}] Plagiarism check failed")
        async with Session() as db:
            report = await db.get(PlagiarismReport, report_id)
            if report:
                report.status = "failed"
                await db.commit()
        raise
