from fastapi import HTTPException, status


async def merge_submissions(submissions, db):
    try:
        for submission in submissions:
            await db.merge(submission)
        await db.commit()
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
