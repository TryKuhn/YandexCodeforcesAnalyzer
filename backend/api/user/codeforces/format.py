from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Contest, Task, ContestParticipant, TaskResult, Submission


def format_codeforces_standings(standings: Dict[str, dict], user_id: int, unofficial: bool) -> Tuple[
    Contest, List[Task], List[ContestParticipant]]:
    contest = standings['contest']
    problems = standings['problems']
    rows = standings['rows']

    start_time = None
    if 'startTimeSeconds' in contest:
        start_time = datetime.fromtimestamp(contest['startTimeSeconds'])

    formatted_contest = Contest(
        external_id=contest['id'],
        user_id=user_id,
        platform='cf',
        name=contest['name'],
        type=contest['type'] if contest['type'] != 'CF' else 'ICPC',
        unofficial=unofficial,
        start_time=start_time,
        duration=timedelta(seconds=contest['durationSeconds']),
    )

    best_scores = [0.0] * len(problems)
    for row in rows:
        for idx, problem in enumerate(row['problemResults']):
            points = float(problem.get('points', 0))
            if points > best_scores[idx]:
                best_scores[idx] = points

    formatted_problems: List[Task] = []
    for idx, problem in enumerate(problems):
        max_score = problem.get('points', best_scores[idx])
        formatted_problems.append(Task(
            id=f'cf_{user_id}_{contest["id"]}_{problem["index"]}',
            contest=formatted_contest,
            short_name=problem['index'],
            full_name=problem['name'],
            max_score=max_score,
        ))

    merged_participants = {}
    merged_results = {}

    for row in rows:
        party = row['party']
        login = party['members'][0]['handle'] if 'teamId' not in party else f'team_{party["teamId"]}'
        name = party.get('teamName') or party['members'][0].get('name')

        if login not in merged_participants:
            merged_participants[login] = ContestParticipant(
                login=login,
                name=name,
                score=0.0
            )
            merged_results[login] = {}

        for idx, problem in enumerate(row['problemResults']):
            task_id = formatted_problems[idx].id
            points = float(problem.get('points', 0))
            tries = int(problem.get('rejectedAttemptCount', 0))

            success_time = None
            if points > 0 and start_time and 'bestSubmissionTimeSeconds' in problem:
                success_time = start_time + timedelta(seconds=problem['bestSubmissionTimeSeconds'])

            if task_id in merged_results[login]:
                old_res = merged_results[login][task_id]

                if points > old_res.score:
                    old_res.score = points
                    old_res.last_success_time = success_time
                elif points == old_res.score and success_time:
                    if not old_res.last_success_time or success_time < old_res.last_success_time:
                        old_res.last_success_time = success_time

                old_res.tries_count += tries
            else:
                merged_results[login][task_id] = TaskResult(
                    task_id=task_id,
                    score=points,
                    tries_count=tries,
                    last_success_time=success_time,
                    verdict='NULL',
                    banned=False
                )

    formatted_rows = []
    for login, contest_participant in merged_participants.items():
        total_score = 0.0
        task_results_list = []

        for problem in formatted_problems:
            res = merged_results[login].get(problem.id)
            if not res: continue

            if res.score > 0:
                res.verdict = 'OK' if res.score == problem.max_score else 'PARTIAL'
            elif res.tries_count > 0:
                res.verdict = 'WA'
            else:
                res.verdict = 'NULL'

            total_score += res.score
            task_results_list.append(res)

        contest_participant.score = total_score
        formatted_rows.append((contest_participant, task_results_list))

    return formatted_contest, formatted_problems, formatted_rows


async def format_codeforces_submissions(submissions: List[dict], user_id: int, contest_id: int, db: AsyncSession) -> \
List[Submission]:
    formatted_submissions = []
    for submission in submissions:
        problem = submission['problem']
        problem = await db.execute(select(Task).filter_by(full_name=problem['name'], contest_id=contest_id))
        problem = problem.scalars().first()

        party = submission['author']
        participant_login = party['members'][0]['handle'] if 'teamId' not in party else f'team_{party["teamId"]}'

        participant = await db.execute(
            select(ContestParticipant).filter_by(contest_id=contest_id, login=participant_login))
        participant = participant.scalars().first()

        if not participant:
            continue

        task_result = await db.execute(select(TaskResult).filter_by(task_id=problem.id, contest_participant_id=participant.id))
        task_result = task_result.scalars().first()

        if not task_result:
            continue

        formatted_submission = Submission(
            id=f'cf_{user_id}_{contest_id}_{submission["id"]}',
            contest_id=contest_id,
            task_result_id=task_result.id,
            participant_login=participant_login,
            task_name=problem.full_name,
            send_time=datetime.fromtimestamp(submission['creationTimeSeconds']),
            language=submission['programmingLanguage'],
            score=float(submission.get('points', 0)),
            verdict=submission['verdict'],
            run_time=timedelta(milliseconds=submission['timeConsumedMillis']),
            memory_bytes=int(submission['memoryConsumedBytes']),
            source=submission['sourceBase64'],
        )
        formatted_submissions.append(formatted_submission)

    return formatted_submissions
