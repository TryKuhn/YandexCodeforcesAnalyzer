from fastapi import HTTPException, status
from sqlalchemy import select

from models import Contest, Participant, ContestParticipant, TaskResult


async def merge_table(contest, tasks, rows, user_id, db):
    try:
        contest_copy = await db.execute(select(Contest).filter_by(
            external_id=contest.external_id,
            user_id=user_id
        ))
        contest_copy = contest_copy.scalars().first()

        if contest_copy:
            contest.id = contest_copy.id

        for participant, results in rows:
            global_participant = await db.execute(select(Participant).filter_by(login=participant.login))
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

            participant_copy = await db.execute(select(ContestParticipant).filter_by(
                contest_id=contest.id,
                participant_id=global_participant.id
            ))
            participant_copy = participant_copy.scalars().first()

            if participant_copy:
                participant.id = participant_copy.id

            participant.contest = contest

            for result in results:
                result.contest_participant = participant

                if hasattr(participant, 'id') and participant.id:
                    row_copy = await db.execute(select(TaskResult).filter_by(
                        contest_participant_id=participant.id, task_id=result.task_id
                    ))
                    row_copy = row_copy.scalars().first()
                    if row_copy:
                        result.id = row_copy.id

        await db.merge(contest)
        await db.commit()

        return {
            'message': 'Standings updated successfully',
            'contest_name': contest.name,
        }

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
