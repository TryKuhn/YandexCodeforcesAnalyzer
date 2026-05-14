import asyncio

import httpx
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas import YandexSubmissions
from api.user.merge_submissions import merge_submissions
from api.user.yandex import yandex_router
from api.user.yandex.format import format_yandex_submissions
from app.database import get_db
from models import Contest, User
from settings import settings


@yandex_router.post("/submissions")
async def yandex_submissions(
    submissions: YandexSubmissions,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    method_name = f"contests/{submissions.contest_id}/submissions"

    user = await db.execute(select(User).filter_by(id=user_id))
    user = user.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not user.yandex_access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yandex API is not configured",
        )

    headers = {
        "Authorization": f"OAuth {user.yandex_access_token}",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        params = {
            "page": 1 + (submissions.from_pos // submissions.count),
            "pageSize": submissions.count,
        }

        submissions_info = await client.get(
            f"{settings.YANDEX_HOST}/{method_name}", headers=headers, params=params
        )

        if submissions_info.status_code == 400:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contest standings are not available",
            )
        elif submissions_info.status_code == 401:
            user.yandex_access_token = None
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Your Yandex token has expired and was automatically unlinked. Please re-connect your account.",
            )
        elif submissions_info.status_code == 403:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to contest",
            )
        elif submissions_info.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found"
            )
        elif submissions_info.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch standings",
            )

        submissions_info = submissions_info.json()["submissions"]

        async def fetch_source(submission_info):
            source_url = (
                f'{settings.YANDEX_HOST}/{method_name}/{submission_info["id"]}/source'
            )
            try:
                submission_source = await client.get(source_url, headers=headers)
                submission_info["source"] = (
                    submission_source.text
                    if submission_source.status_code == 200
                    else ""
                )
            except Exception:
                submission_info["source"] = ""
            return submission_info

        tasks = [fetch_source(submission_info) for submission_info in submissions_info]
        submissions_info = await asyncio.gather(*tasks)

    contest = await db.execute(
        select(Contest).filter_by(external_id=submissions.contest_id)
    )
    contest = contest.scalars().first()

    if not contest:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Contest not found in database",
        )

    submissions_result = await format_yandex_submissions(
        submissions_info, user_id, contest.id, db
    )

    return await merge_submissions(submissions_result, db)
