from time import time

from aiohttp import ClientSession
from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from yarl import URL

from api.crypt import get_current_user
from api.pydantic_schemas import Standings
from api.user.codeforces import codeforces_router
from api.user.codeforces.create_signature import create_signature
from api.user.codeforces.format import format_codeforces_standings
from api.user.codeforces.get_response import get_response
from api.user.merge_table import merge_table
from app.database import get_db
from models import User
from settings import settings


@codeforces_router.post("/standings")
async def codeforces_standings(
    standings: Standings,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    method_name = "contest.standings"

    user = await db.execute(select(User).filter_by(id=user_id))
    user = user.scalars().first()

    if not user.codeforces_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Codeforces API is not configured",
        )

    api_key = str(user.codeforces_api_key)
    api_secret = str(user.codeforces_api_secret)
    current_time_unix = int(time())

    params = {
        "apiKey": api_key,
        "time": str(current_time_unix),
        "contestId": standings.contest_id,
        "asManager": standings.as_manager,
        "from": standings.from_pos,
        "count": standings.count,
        "showUnofficial": standings.show_unofficial,
    }

    signature = await create_signature(method_name, params, api_secret)
    params["apiSig"] = signature

    url = URL(settings.CODEFORCES_HOST) / method_name

    async with ClientSession() as client:
        response = await get_response(client, url, params)

    contest, tasks, rows = format_codeforces_standings(
        response, user_id, standings.show_unofficial
    )

    return await merge_table(contest, tasks, rows, user_id, db)
