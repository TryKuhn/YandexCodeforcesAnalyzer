"""Plagiarism detection API: report generation/listing, submission and
task-result banning, and per-task similarity checks run via the native
``plagiarism_cpp`` extension in a process pool.
"""
import asyncio
import logging
import re
from base64 import b64decode
from concurrent.futures import ProcessPoolExecutor
from math import ceil

import plagiarism_cpp
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
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

_LANG_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'pypy',               re.IGNORECASE), 'PyPy'),
    (re.compile(r'c\+\+|g\+\+',        re.IGNORECASE), 'C++'),
    (re.compile(r'python|py[23]\b',     re.IGNORECASE), 'Python'),
    (re.compile(r'java(?!script)',       re.IGNORECASE), 'Java'),
    (re.compile(r'kotlin',              re.IGNORECASE), 'Kotlin'),
    (re.compile(r'c#|csharp',           re.IGNORECASE), 'C#'),
    (re.compile(r'gnu\s*c\b|gnu\s*c\d', re.IGNORECASE), 'C'),
    (re.compile(r'rust',                re.IGNORECASE), 'Rust'),
    (re.compile(r'\bgo\b|golang',       re.IGNORECASE), 'Go'),
    (re.compile(r'haskell',             re.IGNORECASE), 'Haskell'),
    (re.compile(r'javascript|node\.?js',re.IGNORECASE), 'JavaScript'),
    (re.compile(r'typescript',          re.IGNORECASE), 'TypeScript'),
    (re.compile(r'ruby',                re.IGNORECASE), 'Ruby'),
    (re.compile(r'scala',               re.IGNORECASE), 'Scala'),
    (re.compile(r'swift',               re.IGNORECASE), 'Swift'),
    (re.compile(r'\bphp\b',             re.IGNORECASE), 'PHP'),
    (re.compile(r'\bperl\b',            re.IGNORECASE), 'Perl'),
    (re.compile(r'pascal|delphi',       re.IGNORECASE), 'Pascal'),
    (re.compile(r'ocaml',               re.IGNORECASE), 'OCaml'),
    (re.compile(r'clojure',             re.IGNORECASE), 'Clojure'),
    (re.compile(r'\bd\b',               re.IGNORECASE), 'D'),
]


def _normalize_language_display(lang: str) -> str:
    """Collapse versioned/compiler-specific language strings to a canonical name.

    Patterns in ``_LANG_PATTERNS`` are checked top-to-bottom and the first
    match wins, so more specific entries come first (PyPy before Python, C++
    before C).

    Examples:
        "GNU G++17 7.3.0"   -> "C++"
        "Python 3.11"       -> "Python"
        "PyPy 3-64"         -> "PyPy"
        "Java 17"           -> "Java"
        "Kotlin 1.9"        -> "Kotlin"
    """
    for pattern, canonical in _LANG_PATTERNS:
        if pattern.search(lang):
            return canonical
    return lang


_plagiarism_executor = ProcessPoolExecutor(max_workers=4)


def _run_plagiarism_check(sub_rows: list, threshold: float) -> list[tuple]:
    """Compute similar submission pairs for one task group, in a subprocess.

    Runs in a ``_plagiarism_executor`` worker (separate GIL) so the C++
    similarity computation never blocks the event loop. Returns plain
    ``(first_id, second_id, percent)`` tuples so the result is picklable.
    """
    import logging
    import os
    _log = logging.getLogger(__name__)
    _log.info(
        f"[plagiarism worker] pid={os.getpid()} cwd={os.getcwd()} "
        f"submissions={len(sub_rows)} threshold={threshold}"
    )
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
    _log.info(f"[plagiarism worker] pid={os.getpid()} returned {len(pairs)} pairs")
    return [
        (
            str(pair.first_submission_id),
            str(pair.second_submission_id),
            pair.plagiarism_percent,
        )
        for pair in pairs
    ]


class PlagiarismCheckBody(BaseModel):
    """Parameters for launching a plagiarism check.

    ``threshold`` is the [0, 1] similarity cutoff passed to the C++ engine;
    ``banThreshold`` is the [0, 1] auto-ban cutoff (expected >= ``threshold``).
    ``languages``/``tasks`` optionally restrict which submissions are compared.
    """

    threshold: float = Field(ge=0.0, le=1.0)
    banThreshold: float = Field(ge=0.0, le=1.0)
    onlyOk: bool = False
    languages: list[str] | None = None
    tasks: list[str] | None = None


@router.get("/contests/{contest_id}/reports")
async def get_contest_reports(
    contest_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List a contest's plagiarism reports (newest first) with pair counts."""
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
    """Return the distinct normalized languages and task names for a contest.

    Used to populate the plagiarism-check filter options.
    """
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

    raw_langs = [lang for lang in languages_result.scalars().all() if lang]
    normalized_langs = sorted(set(_normalize_language_display(lang) for lang in raw_langs))

    return {
        "languages": normalized_langs,
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
    """Return a paginated page of a completed report's suspicious pairs.

    Supports filtering by task name and searching by participant login.
    Participant display names are batch-loaded for the page, and the set of
    tasks that already have banned submissions is included.
    """
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

    _fb_q = await db.execute(
        select(Submission.task_name).distinct()
        .join(PairOfBannedSubmissions, PairOfBannedSubmissions.first_submission_id == Submission.id)
        .filter(PairOfBannedSubmissions.report_id == report_id, Submission.banned.is_(True))
    )
    _sb_q = await db.execute(
        select(Submission.task_name).distinct()
        .join(PairOfBannedSubmissions, PairOfBannedSubmissions.second_submission_id == Submission.id)
        .filter(PairOfBannedSubmissions.report_id == report_id, Submission.banned.is_(True))
    )
    banned_tasks = list(
        {t for t in _fb_q.scalars().all() if t} |
        {t for t in _sb_q.scalars().all() if t}
    )

    return {
        "id": report.id,
        "status": report.status,
        "tasks": available_tasks,
        "banned_tasks": banned_tasks,
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
    """Return full detail for one suspicious pair, including both sources.

    Decodes each submission's source, resolves participant names, and reports
    each side's pre-ban score and current banned state.
    """
    _pair_q = await db.execute(
        select(PairOfBannedSubmissions)
        .options(
            joinedload(PairOfBannedSubmissions.first_submission).joinedload(Submission.task_result),
            joinedload(PairOfBannedSubmissions.second_submission).joinedload(Submission.task_result),
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

    def _decode_source(raw: str | None) -> str:
        """Base64-decode stored source, falling back to the raw value on error."""
        if not raw:
            return ""
        try:
            return b64decode(raw).decode("utf-8", errors="replace")
        except Exception:
            return raw

    def _original_score(sub: Submission) -> float | None:
        """Return the score the participant earned before any ban.

        A banned task_result has its score zeroed, so the value is recovered
        from the submission itself in that case.
        """
        tr = sub.task_result
        if tr is None:
            return sub.score
        return sub.score if tr.banned else tr.score

    return {
        "id": pair.id,
        "percent": round(pair.percentage, 2),
        "task_name": pair.first_submission.task_name,
        "user1": login1,
        "user1_name": name_map.get(login1),
        "user2": login2,
        "user2_name": name_map.get(login2),
        "sub1_id": str(pair.first_submission_id),
        "sub2_id": str(pair.second_submission_id),
        "code1": _decode_source(pair.first_submission.source),
        "code2": _decode_source(pair.second_submission.source),
        "sub1_banned": pair.first_submission.banned,
        "sub2_banned": pair.second_submission.banned,
        "score1": _original_score(pair.first_submission),
        "score2": _original_score(pair.second_submission),
    }


@router.post("/reports/{report_id}/ban-task")
async def ban_report_task(
    report_id: int,
    task_name: str | None = Query(None),
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ban every submission that appears in the report's pairs (optionally filtered by task)."""
    _report_q = await db.execute(select(PlagiarismReport).filter_by(id=report_id))
    report = _report_q.scalars().first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    _contest_q = await db.execute(
        select(Contest).filter_by(id=report.contest_id, user_id=user_id)
    )
    if not _contest_q.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found")

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

    _pairs_q = await db.execute(query)
    pairs = _pairs_q.scalars().all()

    sub_ids: set[str] = set()
    for pair in pairs:
        sub_ids.add(str(pair.first_submission_id))
        sub_ids.add(str(pair.second_submission_id))

    for sub_id in sub_ids:
        await _ban_task_result_for_submission(db, sub_id)

    await db.commit()
    return {"banned_submissions": len(sub_ids)}


@router.post("/reports/{report_id}/unban-task")
async def unban_report_task(
    report_id: int,
    task_name: str | None = Query(None),
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Unban every submission that appears in the report's pairs.

    Pass ``task_name`` to limit the action to one task; omit it to unban
    all tasks in the report at once.
    """
    _report_q = await db.execute(select(PlagiarismReport).filter_by(id=report_id))
    report = _report_q.scalars().first()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    _contest_q = await db.execute(
        select(Contest).filter_by(id=report.contest_id, user_id=user_id)
    )
    if not _contest_q.scalars().first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found")

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

    _pairs_q = await db.execute(query)
    pairs = _pairs_q.scalars().all()

    sub_ids: set[str] = set()
    for pair in pairs:
        sub_ids.add(str(pair.first_submission_id))
        sub_ids.add(str(pair.second_submission_id))

    for sub_id in sub_ids:
        await _unban_task_result_for_submission(db, sub_id)

    await db.commit()
    return {"unbanned_submissions": len(sub_ids)}


@router.post("/pairs/{pair_id}/ban/{position}")
async def ban_pair_submission(
    pair_id: int,
    position: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Ban the task result behind one side (``position`` 1 or 2) of a pair."""
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
    """Unban the task result behind one side (``position`` 1 or 2) of a pair."""
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
    """Create a processing report and launch the check as a background task.

    Returns the new report id immediately; results are filled in asynchronously
    by ``process_plagiarism_report``.
    """
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
    """Run a contest's plagiarism check end to end and persist the results.

    Steps: load matching submissions (with optional verdict/language/task
    filters) and release the DB connection; keep only the last submission per
    (participant, task); group by task so the C++ LSH runs per-task (cross-task
    pairs are irrelevant and would bloat the O(n^2) candidate set); dispatch
    each group to the process pool in parallel; persist the resulting pairs and
    mark the report completed; finally auto-ban pairs at or above
    ``ban_threshold``. Marks the report ``failed`` and re-raises on error.

    Normalized language names (e.g. "C++") are expanded back to the raw
    submission language strings before filtering.
    """
    try:
        async with Session() as db:
            query = select(Submission).filter_by(contest_id=contest_id)
            if only_ok:
                query = query.filter_by(verdict="OK")
            if languages:
                raw_q = await db.execute(
                    select(Submission.language).distinct().filter_by(contest_id=contest_id)
                )
                all_raw = [lang for lang in raw_q.scalars().all() if lang]
                wanted = set(languages)
                matching_raw = [lang for lang in all_raw if _normalize_language_display(lang) in wanted]
                if matching_raw:
                    query = query.filter(Submission.language.in_(matching_raw))
                else:
                    query = query.filter(Submission.language.in_([]))
            if tasks:
                query = query.filter(Submission.task_name.in_(tasks))

            submissions_result = await db.execute(query)
            submissions = submissions_result.scalars().all()

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

        task_groups: dict[str, list[dict]] = {}
        for sub in sub_rows:
            task_groups.setdefault(sub["task_name"] or "", []).append(sub)

        logger.info(
            f"[report={report_id}] {len(sub_rows)} unique (participant, task) submissions "
            f"after dedup (raw={len(submissions)}) across {len(task_groups)} tasks "
            f"(contest={contest_id}, threshold={threshold})"
        )

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
