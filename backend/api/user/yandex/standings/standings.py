import httpx
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas import YandexStandings
from api.user.merge_table import merge_table
from api.user.yandex import yandex_router
from api.user.yandex.format import format_yandex_standings
from app.database import get_db
from models import User
from settings import settings


@yandex_router.post("/standings")
async def yandex_standings(
    standings: YandexStandings,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    method_name = f"contests/{standings.contest_id}"

    user = await db.execute(select(User).filter_by(id=user_id))
    user = user.scalars().first()

    if not user.yandex_access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Yandex API is not configured",
        )

    headers = {
        "Authorization": f"OAuth {user.yandex_access_token}",
    }

    async with httpx.AsyncClient() as client:
        contest_info = await client.get(
            f"{settings.YANDEX_HOST}/{method_name}", headers=headers
        )

        if contest_info.status_code == 400:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Contest standings are not available",
            )
        elif contest_info.status_code == 401:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Your token expired or invalid",
            )
        elif contest_info.status_code == 403:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to contest",
            )
        elif contest_info.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Contest not found"
            )
        elif contest_info.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch standings",
            )

        contest_info = contest_info.json()
        contest_info["id"] = standings.contest_id

        params = {
            "forJudge": "true" if standings.as_manager else "false",
            "page": 1 + (standings.from_pos // standings.count),
            "pageSize": standings.count,
            "showExternal": "true" if standings.show_unofficial else "false",
            "showVirtual": "true" if standings.show_unofficial else "false",
        }

        standings_data = await client.get(
            f"{settings.YANDEX_HOST}/{method_name}/standings",
            params=params,
            headers=headers,
        )

        if standings_data.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to fetch standings",
            )
        standings_data = standings_data.json()

    contest, tasks, rows = format_yandex_standings(
        contest_info, standings_data, user_id, standings.show_unofficial
    )

    return await merge_table(contest, tasks, rows, user_id, db)
