from base64 import b64encode
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import Contest, ContestParticipant, Submission, Task, TaskResult


def format_yandex_standings(
    contest_info: dict, standings: Dict[str, dict], user_id: int, unofficial: bool
) -> Tuple[Contest, List[Task], List[ContestParticipant]]:
    contest = contest_info
    problems = standings.get("titles", [])
    rows = standings.get("rows", [])

    start_time = None
    if "startTime" in contest:
        try:
            start_time = datetime.fromisoformat(
                contest["startTime"].replace("Z", "+00:00")
            ).replace(tzinfo=None)
        except (KeyError, TypeError, ValueError):
            start_time = None

    contest_type = "ICPC" if contest_info["standingsPlugin"] == "acm" else "IOI"
    best_scores = [0.0] * len(problems)
    for row in rows:
        for idx, problem in enumerate(row["problemResults"]):
            if problem["score"] == "":
                points = int(problem["status"] == "ACCEPTED")
            else:
                points = float(problem["score"])

            if points > best_scores[idx]:
                best_scores[idx] = points

    print(best_scores)

    formatted_contest = Contest(
        external_id=contest["id"],
        user_id=user_id,
        platform="yandex",
        name=contest["name"],
        type=contest_type,
        unofficial=unofficial,
        start_time=start_time,
        duration=timedelta(seconds=contest.get("duration", 0)),
    )

    formatted_problems: List[Task] = []
    for idx, problem in enumerate(problems):
        max_score = best_scores[idx]
        formatted_problems.append(
            Task(
                id=f'ya_{user_id}_{contest["id"]}_{problem["id"]}',
                contest=formatted_contest,
                short_name=problem["title"],
                full_name=problem["name"],
                max_score=max_score,
            )
        )

    merged_participants = {}
    merged_results = {}

    for row in rows:
        login = row["participantInfo"]["login"]
        name = row["participantInfo"]["name"]

        if login not in merged_participants:
            merged_participants[login] = ContestParticipant(
                login=login, name=name, score=0.0
            )
            merged_results[login] = {}

        for idx, problem in enumerate(row["problemResults"]):
            task_id = formatted_problems[idx].id
            if problem["score"] == "":
                points = int(problem["status"] == "ACCEPTED")
            else:
                points = float(problem["score"])
            tries = int(problem.get("submissionCount", 1)) - 1

            success_time = None
            if points > 0 and start_time and "submitDelay" in problem:
                success_time = start_time + timedelta(seconds=problem["submitDelay"])

            if task_id in merged_results[login]:
                old_res = merged_results[login][task_id]

                if points > old_res.score:
                    old_res.score = points
                    old_res.last_success_time = success_time
                elif points == old_res.score and success_time:
                    if (
                        not old_res.last_success_time
                        or success_time < old_res.last_success_time
                    ):
                        old_res.last_success_time = success_time

                old_res.tries_count += tries
            else:
                merged_results[login][task_id] = TaskResult(
                    task_id=task_id,
                    score=points,
                    tries_count=tries,
                    last_success_time=success_time,
                    verdict="NULL",
                    banned=False,
                )

    formatted_rows = []
    for login, contest_participant in merged_participants.items():
        total_score = 0.0
        task_results_list = []

        for problem in formatted_problems:
            res = merged_results[login].get(problem.id)
            if not res:
                continue

            if res.score > 0:
                res.verdict = "OK" if res.score == problem.max_score else "PARTIAL"
            elif res.tries_count > 0:
                res.verdict = "WA"
            else:
                res.verdict = "NULL"

            total_score += res.score
            task_results_list.append(res)

        contest_participant.score = total_score
        formatted_rows.append((contest_participant, task_results_list))

    return formatted_contest, formatted_problems, formatted_rows


async def format_yandex_submissions(
    submissions: Tuple[Any], user_id: int, contest_id: int, db: AsyncSession
) -> List[Submission]:
    formatted_submissions = []
    for submission in submissions:
        print(submission)

        problem = await db.execute(
            select(Task).filter_by(
                short_name=submission["problemAlias"], contest_id=contest_id
            )
        )
        problem = problem.scalars().first()

        participant_name = submission["author"]

        participant = await db.execute(
            select(ContestParticipant).filter_by(
                contest_id=contest_id, name=participant_name
            )
        )
        participant = participant.scalars().first()

        if not participant:
            continue

        task_result = await db.execute(
            select(TaskResult).filter_by(
                task_id=problem.id, contest_participant_id=participant.id
            )
        )
        task_result = task_result.scalars().first()

        if not task_result:
            continue

        if submission["score"] == "" or submission["score"] is None:
            points = int(submission["verdict"] == "ACCEPTED")
        else:
            points = float(submission["score"])

        formatted_submission = Submission(
            id=f'yandex_{user_id}_{contest_id}_{submission["id"]}',
            contest_id=contest_id,
            task_result_id=task_result.id,
            participant_login=participant.login,
            task_name=problem.full_name,
            send_time=datetime.fromisoformat(
                submission["submissionTime"].replace("Z", "+00:00")
            ).replace(tzinfo=None),
            language=submission["compiler"],
            score=points,
            verdict=submission["verdict"],
            run_time=timedelta(milliseconds=submission["time"]),
            memory_bytes=int(submission["memory"]),
            source=b64encode(submission["source"].encode("utf-8")).decode("utf-8"),
        )
        formatted_submissions.append(formatted_submission)

    return formatted_submissions
