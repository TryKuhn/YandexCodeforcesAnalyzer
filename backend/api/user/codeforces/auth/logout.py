"""Endpoint for unlinking a user's Codeforces API credentials."""
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.user.codeforces.base_codeforces import router as codeforces_router
from app.database import get_db
from models import User


@codeforces_router.post("/unlink")
async def unlink_codeforces(
    user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """Clear the stored Codeforces API key/secret for the current user."""
    user = await db.execute(select(User).filter_by(id=user_id))
    user = user.scalars().first()

    user.codeforces_api_key = None
    user.codeforces_api_secret = None
    # user.codeforces_access_token = None
    await db.commit()

    return {"message": "Codeforces account successfully unlinked"}
