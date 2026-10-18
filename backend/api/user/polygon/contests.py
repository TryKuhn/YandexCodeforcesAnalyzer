"""``/api/polygon/contests`` — Polygon contest routes."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.user.polygon.methods import get_contest_problems
from app.database import get_db

contests_router = APIRouter(prefix="/contests")


@contests_router.get("/{contest_id}/problems")
async def route_get_contest_problems(
    contest_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Problems of a Polygon contest keyed by their letter."""
    return await get_contest_problems(contest_id, user_id, db)
