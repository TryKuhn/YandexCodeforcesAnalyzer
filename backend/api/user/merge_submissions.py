"""Idempotent upsert of formatted submissions into the database."""
from fastapi import HTTPException, status


async def merge_submissions(submissions, db):
    """Upsert a list of Submission objects, rolling back and raising HTTP 500 on error."""
    try:
        for submission in submissions:
            await db.merge(submission)
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )
