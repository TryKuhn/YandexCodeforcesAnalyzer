from base64 import b64decode
from math import ceil

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.params import Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from app.database import get_db
from models import Contest, ContestParticipant, Submission, Task, TaskResult

contest_router = APIRouter()


@contest_router.get("/list")
async def get_user_contests(
    user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    contests = await db.execute(
        select(Contest).filter_by(user_id=user_id).order_by(Contest.id.desc())
    )
    contests = contests.scalars().all()

    return [
        {
            "id": contest.id,
            "name": contest.name,
            "platform": contest.platform,
            "external_id": contest.external_id,
            "type": contest.type,
            "unofficial": contest.unofficial,
            "start_time": (
                contest.start_time.isoformat() if contest.start_time else None
            ),
            "duration": contest.duration if contest.duration else None,
        }
        for contest in contests
    ]


@contest_router.get("/{contest_id}/overview")
async def get_contest_overview(
    contest_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    contest = await db.execute(select(Contest).filter_by(id=contest_id))
    contest = contest.scalars().first()

    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")

    tasks_count = await db.execute(
        select(func.count(Task.id)).filter_by(contest_id=contest_id)
    )
    participants_count = await db.execute(
        select(func.count(ContestParticipant.id)).filter_by(contest_id=contest_id)
    )
    submissions_count = await db.execute(
        select(func.count(Submission.id)).filter_by(contest_id=contest_id)
    )

    return {
        "id": contest.id,
        "name": contest.name,
        "external_id": contest.external_id,  # Тот самый ID для Codeforces
        "start_time": contest.start_time,
        "type": contest.platform,  # 'cf' или 'yandex'
        "stats": {
            "tasks": tasks_count.scalar(),
            "participants": participants_count.scalar(),
            "submissions": submissions_count.scalar(),
        },
    }


@contest_router.get("/{contest_id}/table")
async def get_contest_table(
    contest_id: int,
    page: int = Query(1, ge=1, description="Номер страницы"),
    per_page: int = Query(50, ge=10, le=200, description="Участников на странице"),
    search: str = Query("", description="Поиск по имени/логину"),
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    contest = await db.execute(select(Contest).filter_by(id=contest_id))
    contest = contest.scalars().first()

    if not contest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found"
        )

    tasks = await db.execute(
        select(Task).filter_by(contest_id=contest.id).order_by(Task.short_name.asc())
    )
    tasks = tasks.scalars().all()

    participants_query = select(ContestParticipant).filter_by(contest_id=contest.id)
    count_query = select(func.count(ContestParticipant.id)).filter_by(
        contest_id=contest.id
    )

    if search.strip():
        search_filter = f"%{search.strip().lower()}%"
        participants_query = participants_query.filter(
            (func.lower(ContestParticipant.name).like(search_filter))
            | (func.lower(ContestParticipant.login).like(search_filter))
        )
        count_query = count_query.filter(
            (func.lower(ContestParticipant.name).like(search_filter))
            | (func.lower(ContestParticipant.login).like(search_filter))
        )

    total = await db.execute(count_query)
    total = total.scalar()
    total_pages = ceil(total / per_page) if total > 0 else 1

    all_participants = await db.execute(participants_query)
    all_participants = all_participants.scalars().all()

    all_results = await db.execute(
        select(TaskResult).filter(
            TaskResult.contest_participant_id.in_([p.id for p in all_participants])
        )
    )
    all_results = all_results.scalars().all()

    results_by_participant: dict[int, dict[int, TaskResult]] = {}
    for result in all_results:
        results_by_participant.setdefault(result.contest_participant_id, {})[
            result.task_id
        ] = result

    def effective_total(p: ContestParticipant) -> float:
        return sum(
            (r.score or 0)
            for r in results_by_participant.get(p.id, {}).values()
            if not r.banned
        )

    sorted_participants = sorted(all_participants, key=effective_total, reverse=True)

    offset = (page - 1) * per_page
    page_participants = sorted_participants[offset : offset + per_page]

    rows = []
    for rank, participant in enumerate(page_participants, start=offset + 1):
        results_map = results_by_participant.get(participant.id, {})
        total_score = effective_total(participant)

        row_results = []
        for task in tasks:
            result = results_map.get(task.id)
            row_results.append(
                {
                    "score": result.score if result else 0,
                    "verdict": result.verdict if result else "NULL",
                    "tries": result.tries_count if result else 0,
                    "time": (
                        result.last_success_time.isoformat()
                        if result and result.last_success_time
                        else None
                    ),
                    "banned": result.banned if result else False,
                }
            )

        rows.append(
            {
                "id": participant.id,
                "name": participant.name,
                "login": participant.login,
                "rank": rank,
                "total_score": total_score,
                "results": row_results,
            }
        )

    return {
        "contest_name": contest.name,
        "contest_type": contest.type,
        "tasks": [
            {"short_name": t.short_name, "full_name": t.full_name} for t in tasks
        ],
        "rows": rows,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        },
    }


@contest_router.get("/{contest_id}/submissions_list")
async def get_contest_submissions_headers(
    contest_id: int,
    page: int = Query(1, ge=1, description="Номер страницы"),
    per_page: int = Query(50, ge=10, le=200, description="Участников на странице"),
    search: str = Query("", description="Поиск по логину, задаче или ID"),
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    submissions_query = select(Submission).filter_by(contest_id=contest_id)
    count_query = select(func.count(Submission.id)).filter_by(contest_id=contest_id)

    if search.strip():
        search_filter = f"%{search.strip().lower()}%"
        search_condition = (
            (func.lower(Submission.participant_login).like(search_filter))
            | (func.lower(Submission.task_name).like(search_filter))
            | (func.lower(Submission.id).like(search_filter))
        )
        submissions_query = submissions_query.filter(search_condition)
        count_query = count_query.filter(search_condition)

    total = await db.execute(count_query)
    total = total.scalar()
    total_pages = ceil(total / per_page) if total > 0 else 1

    offset = (page - 1) * per_page
    submissions_query = (
        submissions_query.order_by(Submission.send_time.desc())
        .offset(offset)
        .limit(per_page)
    )

    submissions = await db.execute(submissions_query)
    submissions = submissions.scalars().all()

    return {
        "items": [
            {
                "id": submission.id,
                "participant_login": submission.participant_login,
                "task_name": submission.task_name,
                "send_time": submission.send_time,
                "language": submission.language,
                "score": submission.score,
                "verdict": submission.verdict,
            }
            for submission in submissions
        ],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        },
    }


@contest_router.get("/submissions/{submission_id}/source")
async def get_submission_source(
    submission_id: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    submission = await db.execute(select(Submission).filter_by(id=submission_id))
    submission = submission.scalars().first()

    return {
        "id": submission.id,
        "participant_login": submission.participant_login,
        "task_name": submission.task_name,
        "send_time": submission.send_time,
        "language": submission.language,
        "score": submission.score,
        "verdict": submission.verdict,
        "run_time": str(submission.run_time),
        "memory_bytes": str(submission.memory_bytes),
        "banned": submission.banned,
        "source": b64decode(submission.source).decode("utf-8"),
    }


@contest_router.get("/{contest_id}/visual-analytics")
async def get_visual_analytics(
    contest_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    contest_q = await db.execute(
        select(Contest).filter_by(id=contest_id, user_id=user_id)
    )
    contest = contest_q.scalars().first()
    if not contest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found"
        )

    tasks_q = await db.execute(
        select(Task).filter_by(contest_id=contest_id).order_by(Task.short_name.asc())
    )
    tasks = tasks_q.scalars().all()

    short_names_set = {t.short_name for t in tasks}
    full_to_short = {t.full_name: t.short_name for t in tasks}
    short_to_full = {t.short_name: t.full_name for t in tasks}
    task_names = [t.short_name for t in tasks]

    def to_short(sub_task_name: str) -> str | None:
        if sub_task_name in short_names_set:
            return sub_task_name
        return full_to_short.get(sub_task_name)

    subs_q = await db.execute(select(Submission).filter_by(contest_id=contest_id))
    submissions = subs_q.scalars().all()

    parts_q = await db.execute(
        select(ContestParticipant).filter_by(contest_id=contest_id)
    )
    participants = parts_q.scalars().all()
    n_participants = len(participants)

    start_time = contest.start_time
    if not start_time and submissions:
        start_time = min(s.send_time for s in submissions)

    BUCKET_MIN = 15
    task_buckets: dict[str, dict[int, dict]] = {name: {} for name in task_names}
    for sub in submissions:
        if not start_time or not sub.task_name:
            continue
        short = to_short(sub.task_name)
        if short is None:
            continue
        delta = int((sub.send_time - start_time).total_seconds() / 60)
        if delta < 0:
            continue
        b = (delta // BUCKET_MIN) * BUCKET_MIN
        entry = task_buckets[short].setdefault(b, {"total": 0, "ok": 0})
        entry["total"] += 1
        if sub.verdict == "OK":
            entry["ok"] += 1

    submissions_over_time: dict[str, list] = {}
    for name, buckets in task_buckets.items():
        if not buckets:
            submissions_over_time[name] = []
            continue
        max_b = max(buckets)
        submissions_over_time[name] = [
            {
                "label": f"{b // 60:02d}:{b % 60:02d}",
                "total": buckets.get(b, {"total": 0, "ok": 0})["total"],
                "ok": buckets.get(b, {"total": 0, "ok": 0})["ok"],
            }
            for b in range(0, max_b + BUCKET_MIN, BUCKET_MIN)
        ]

    subs_by_task: dict[str, list] = {name: [] for name in task_names}
    for sub in submissions:
        short = to_short(sub.task_name or "")
        if short:
            subs_by_task[short].append(sub)

    task_stats = []
    for name in task_names:
        task_subs = subs_by_task[name]
        if not task_subs:
            continue
        total = len(task_subs)
        ok = sum(1 for s in task_subs if s.verdict == "OK")
        wa = sum(1 for s in task_subs if s.verdict == "WA")
        tle = sum(
            1
            for s in task_subs
            if (s.verdict or "").upper() in ("TL", "TLE", "TIME_LIMIT_EXCEEDED")
        )
        re = sum(
            1 for s in task_subs if (s.verdict or "").upper() in ("RE", "RUNTIME_ERROR")
        )
        other = max(0, total - ok - wa - tle - re)
        solvers = len({s.participant_login for s in task_subs if s.verdict == "OK"})
        task_stats.append(
            {
                "task": name,
                "full_name": short_to_full.get(name, name),
                "total": total,
                "ok": ok,
                "wa": wa,
                "tle": tle,
                "re": re,
                "other": other,
                "solvers": solvers,
                "solve_rate": (
                    round(solvers / n_participants * 100, 1) if n_participants else 0
                ),
            }
        )

    scores = [p.score for p in participants if p.score is not None]
    score_distribution: list[dict] = []
    if scores:
        max_score = max(scores)
        n_buckets = 10
        bucket_size = max(1.0, max_score / n_buckets)
        dist: dict[float, int] = {}
        for sc in scores:
            k = int(sc // bucket_size) * bucket_size
            dist[k] = dist.get(k, 0) + 1
        score_distribution = [
            {"range": f"{int(k)}–{int(k + bucket_size)}", "count": v}
            for k, v in sorted(dist.items())
        ]

    lang_counts: dict[str, int] = {}
    for sub in submissions:
        lang = sub.language or "Unknown"
        lang_counts[lang] = lang_counts.get(lang, 0) + 1
    language_breakdown = sorted(
        [{"language": k, "count": v} for k, v in lang_counts.items()],
        key=lambda x: -x["count"],
    )[:12]

    first_solves: list[dict] = []
    if start_time:
        best: dict[str, dict] = {}
        for sub in submissions:
            if sub.verdict != "OK" or not sub.task_name:
                continue
            short = to_short(sub.task_name)
            if not short:
                continue
            delta = int((sub.send_time - start_time).total_seconds() / 60)
            if short not in best or delta < best[short]["minute"]:
                best[short] = {
                    "task": short,
                    "full_name": short_to_full.get(short, short),
                    "login": sub.participant_login,
                    "minute": delta,
                }
        first_solves = sorted(
            best.values(),
            key=lambda x: (
                task_names.index(x["task"]) if x["task"] in task_names else 999
            ),
        )

    return {
        "contest_name": contest.name,
        "tasks": task_names,
        "submissions_over_time": submissions_over_time,
        "task_stats": task_stats,
        "score_distribution": score_distribution,
        "language_breakdown": language_breakdown,
        "first_solves": first_solves,
    }


@contest_router.delete("/{contest_id}")
async def delete_contest(
    contest_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Contest).filter_by(id=contest_id, user_id=user_id))
    contest = result.scalars().first()

    if not contest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found"
        )

    await db.delete(contest)
    await db.commit()

    return {"message": "Contest deleted successfully"}
