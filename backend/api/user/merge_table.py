from fastapi import HTTPException, status
from sqlalchemy import select

from models import Contest, ContestParticipant, Participant, TaskResult


async def merge_table(contest, tasks, rows, user_id, db):
    try:
        contest_copy = await db.execute(
            select(Contest).filter_by(external_id=contest.external_id, user_id=user_id)
        )
        contest_copy = contest_copy.scalars().first()

        if contest_copy:
            contest.id = contest_copy.id

        prepared = []
        for participant, results in rows:
            global_participant = await db.execute(
                select(Participant).filter_by(login=participant.login)
            )
            global_participant = global_participant.scalars().first()

            if not global_participant:
                global_participant = Participant(
                    user_id=user_id,
                    login=participant.login,
                    name=participant.name,
                )
                db.add(global_participant)
                await db.flush()

            participant.participant_id = global_participant.id

            if contest.id:
                participant_copy = await db.execute(
                    select(ContestParticipant).filter_by(
                        contest_id=contest.id, participant_id=global_participant.id
                    )
                )
                participant_copy = participant_copy.scalars().first()
                if participant_copy:
                    participant.id = participant_copy.id

            for result in results:
                if participant.id:
                    row_copy = await db.execute(
                        select(TaskResult).filter_by(
                            contest_participant_id=participant.id,
                            task_id=result.task_id,
                        )
                    )
                    row_copy = row_copy.scalars().first()
                    if row_copy:
                        result.id = row_copy.id

            prepared.append((participant, results))

        merged_contest = await db.merge(contest)
        await db.flush()

        for participant, results in prepared:
            participant.contest_id = merged_contest.id
            merged_participant = await db.merge(participant)
            if not participant.id:
                await db.flush()

            for result in results:
                result.contest_participant_id = merged_participant.id
                await db.merge(result)

        await db.commit()

        return {
            "message": "Standings updated successfully",
            "contest_name": contest.name,
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
