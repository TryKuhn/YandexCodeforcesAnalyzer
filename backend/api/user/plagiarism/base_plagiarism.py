import asyncio

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from app.database import get_db, Session
from models import Contest, Submission
from models.submissions.plagiarism_report import PlagiarismReport
from models.submissions.pair_of_banned_submissions import PairOfBannedSubmissions
from base64 import b64decode
import plagiarism_cpp

router = APIRouter()


class PlagiarismCheckBody(BaseModel):
    threshold: float
    onlyOk: bool = False


@router.get('/contests/{contest_id}/reports')
async def get_contest_reports(
    contest_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    contest = await db.execute(select(Contest).filter_by(id=contest_id, user_id=user_id))
    contest = contest.scalars().first()

    if not contest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Contest not found')

    reports = await db.execute(
        select(PlagiarismReport)
        .filter_by(contest_id=contest_id)
        .order_by(PlagiarismReport.id.desc())
    )
    reports = reports.scalars().all()

    return [
        {
            'id': report.id,
            'contest_id': report.contest_id,
            'status': report.status,
            'threshold': report.threshold,
            'only_ok': report.only_ok,
            'created_at': report.created_at,
            'updated_at': report.updated_at,
        }
        for report in reports
    ]


@router.get('/reports/{report_id}')
async def get_report(
    report_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    report = await db.execute(select(PlagiarismReport).filter_by(id=report_id))
    report = report.scalars().first()

    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Report not found')

    contest = await db.execute(select(Contest).filter_by(id=report.contest_id, user_id=user_id))
    contest = contest.scalars().first()

    if not contest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Contest not found')

    pairs = await db.execute(
        select(PairOfBannedSubmissions)
        .filter_by(report_id=report_id)
        .order_by(PairOfBannedSubmissions.percentage.desc())
    )
    pairs = pairs.scalars().all()

    return {
        'id': report.id,
        'contest_id': report.contest_id,
        'status': report.status,
        'pairs': [
            {
                'id': pair.id,
                'first_submission_id': pair.first_submission_id,
                'second_submission_id': pair.second_submission_id,
                'plagiarism_percent': pair.percentage,
            }
            for pair in pairs
        ]
    }


@router.get('/pairs/{pair_id}')
async def get_pair(
    pair_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    pair = await db.execute(select(PairOfBannedSubmissions).filter_by(id=pair_id))
    pair = pair.scalars().first()

    if not pair:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Pair not found')

    contest = await db.execute(select(Contest).filter_by(id=pair.contest_id, user_id=user_id))
    contest = contest.scalars().first()

    if not contest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Contest not found')

    first_submission = await db.execute(select(Submission).filter_by(id=pair.first_submission_id))
    first_submission = first_submission.scalars().first()

    second_submission = await db.execute(select(Submission).filter_by(id=pair.second_submission_id))
    second_submission = second_submission.scalars().first()

    if not first_submission or not second_submission:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Submission not found')

    return {
        'id': pair.id,
        'plagiarism_percent': pair.percentage,
        'code1': first_submission.source or '',
        'code2': second_submission.source or '',
    }


@router.post('/contests/{contest_id}/check')
async def run_plagiarism_check(
    contest_id: int,
    body: PlagiarismCheckBody,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    contest = await db.execute(select(Contest).filter_by(id=contest_id, user_id=user_id))
    contest = contest.scalars().first()

    if not contest:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='Contest not found')

    report = PlagiarismReport(
        contest_id=contest_id,
        status='processing',
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
        'reportId': report.id,
        'status': 'processing',
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
                query = query.filter_by(verdict='OK')

            submissions_result = await db.execute(query)
            submissions = submissions_result.scalars().all()

            py_submissions = []
            local_to_real_id = {}

            local_id = 1
            for submission in submissions:
                if not submission.source:
                    continue

                py_sub = plagiarism_cpp.Submission()
                py_sub.id = local_id
                py_sub.language = plagiarism_cpp.ProgrammingLanguage.Cpp
                decoded_code = b64decode(submission.source).decode('utf-8')
                py_sub.rawCode = decoded_code
                py_sub.participant = submission.participant_login or ''
                py_sub.problem = submission.task_name or ''

                py_submissions.append(py_sub)
                local_to_real_id[local_id] = submission.id
                local_id += 1

            pairs = plagiarism_cpp.compute_similarity_pairs(py_submissions, threshold)

            for pair in pairs:
                first_real_id = local_to_real_id[pair.first_submission_id]
                second_real_id = local_to_real_id[pair.second_submission_id]

                db.add(
                    PairOfBannedSubmissions(
                        contest_id=contest_id,
                        report_id=report_id,
                        first_submission_id=first_real_id,
                        second_submission_id=second_real_id,
                        percentage=pair.plagiarism_percent,
                    )
                )

            report = await db.get(PlagiarismReport, report_id)
            if report:
                report.status = 'completed'

            await db.commit()

        except Exception:
            report = await db.get(PlagiarismReport, report_id)
            if report:
                report.status = 'failed'
                await db.commit()
            raise