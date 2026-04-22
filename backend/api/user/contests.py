from base64 import b64decode

from fastapi import Depends, APIRouter, HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from app.database import get_db
from models import Contest, ContestParticipant, Task, TaskResult, Submission

contest_router = APIRouter()


@contest_router.get('/list')
async def get_user_contests(user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    contests = await db.execute(select(Contest).filter_by(user_id=user_id).order_by(Contest.id.desc()))
    contests = contests.scalars().all()

    return [
        {
            'id': contest.id,
            'name': contest.name,
            'platform': contest.platform,
            'external_id': contest.external_id,
            'type': contest.type,
            'unofficial': contest.unofficial,
            'start_time': contest.start_time.isoformat() if contest.start_time else None,
            'duration': contest.duration if contest.duration else None,
        } for contest in contests
    ]


@contest_router.get('/{contest_id}/overview')
async def get_contest_overview(contest_id: int, db: AsyncSession = Depends(get_db)):
    contest = await db.execute(select(Contest).filter_by(id=contest_id))
    contest = contest.scalars().first()

    if not contest:
        raise HTTPException(status_code=404, detail="Contest not found")

    tasks_count = await db.execute(select(func.count(Task.id)).filter_by(contest_id=contest_id))
    participants_count = await db.execute(select(func.count(ContestParticipant.id)).filter_by(contest_id=contest_id))
    submissions_count = await db.execute(select(func.count(Submission.id)).filter_by(contest_id=contest_id))

    return {
        "id": contest.id,
        "name": contest.name,
        "external_id": contest.external_id,  # Тот самый ID для Codeforces
        "start_time": contest.start_time,
        "type": contest.platform,  # 'cf' или 'yandex'
        "stats": {
            "tasks": tasks_count.scalar(),
            "participants": participants_count.scalar(),
            "submissions": submissions_count.scalar()
        }
    }


@contest_router.get('/{contest_id}/table')
async def get_contest_table(contest_id: int, db: AsyncSession = Depends(get_db)):
    contest = await db.execute(select(Contest).filter_by(id=contest_id))
    contest = contest.scalars().first()

    if not contest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Contest not found')

    tasks = await db.execute(
        select(Task).filter_by(contest_id=contest.id).order_by(Task.short_name.asc())
    )
    tasks = tasks.scalars().all()

    participants = await db.execute(
        select(ContestParticipant)
        .filter_by(contest_id=contest.id)
        .order_by(ContestParticipant.score.desc())
    )
    participants = participants.scalars().all()

    rows = []
    for participant in participants:
        results = await db.execute(
            select(TaskResult).filter_by(contest_participant_id=participant.id)
        )
        results = results.scalars().all()

        results_map = {result.task_id: result for result in results}

        row_results = []
        for task in tasks:
            result = results_map.get(task.id)
            row_results.append({
                'score': result.score if result else 0,
                'verdict': result.verdict if result else 'NULL',
                'tries': result.tries_count if result else 0,
                'time': result.last_success_time.isoformat() if result and result.last_success_time else None
            })

        rows.append({
            'id': participant.id,
            'name': participant.name,
            'login': participant.login,
            'total_score': participant.score,
            'results': row_results
        })

    return {
        'contest_name': contest.name,
        'contest_type': contest.type,
        'tasks': [{'short_name': t.short_name, 'full_name': t.full_name} for t in tasks],
        'rows': rows
    }


@contest_router.get('/{contest_id}/submissions_list')
async def get_contest_submissions_headers(contest_id: int, user_id: int = Depends(get_current_user),
                                          db: AsyncSession = Depends(get_db)):
    submissions = await db.execute(select(Submission).filter_by(contest_id=contest_id).order_by(Submission.id.desc()))
    submissions = submissions.scalars().all()

    return [
        {
            'id': submission.id,
            'participant_login': submission.participant_login,
            'task_name': submission.task_name,
            'send_time': submission.send_time,
            'language': submission.language,
            'score': submission.score,
            'verdict': submission.verdict,
        } for submission in submissions
    ]


@contest_router.get('/submissions/{submission_id}/source')
async def get_submission_source(submission_id: str, user_id: int = Depends(get_current_user),
                                db: AsyncSession = Depends(get_db)):
    submission = await db.execute(select(Submission).filter_by(id=submission_id))
    submission = submission.scalars().first()

    return {
        'id': submission.id,
        'participant_login': submission.participant_login,
        'task_name': submission.task_name,
        'send_time': submission.send_time,
        'language': submission.language,
        'score': submission.score,
        'verdict': submission.verdict,
        'run_time': str(submission.run_time),
        'memory_bytes': str(submission.memory_bytes),
        'banned': submission.banned,
        'source': b64decode(submission.source).decode('utf-8'),
    }


@contest_router.delete('/{contest_id}')
async def delete_contest(contest_id: int, user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Contest).filter_by(id=contest_id, user_id=user_id))
    contest = result.scalars().first()

    if not contest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Contest not found')

    await db.delete(contest)
    await db.commit()

    return {'message': 'Contest deleted successfully'}
