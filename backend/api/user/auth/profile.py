from fastapi import HTTPException, status
from fastapi.params import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user, get_current_payload
from api.user.auth import auth_router
from app.database import get_db
from models import User, RefreshToken


@auth_router.get('/me')
async def get_me(user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    user = await db.execute(select(User).filter_by(id=user_id))
    user = user.scalars().first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found.')

    return {
        'id': user.id,
        'login': user.login,
        'email': user.email,
        'role_id': user.role_id,
        'is_yandex_linked': bool(user.yandex_access_token),
        'is_codeforces_linked': bool(user.codeforces_api_key),
        'is_polygon_linked': bool(user.polygon_api_key)
    }

@auth_router.get('/sessions')
async def get_sessions(payload: dict = Depends(get_current_payload), db: AsyncSession = Depends(get_db)):
    user_id = payload.get('user_id')
    current_sid = payload.get('sid')

    sessions = await db.execute(select(RefreshToken).filter_by(user_id=user_id).order_by(RefreshToken.created_at.desc()))
    sessions = sessions.scalars().all()

    return [
        {
            'id': session.id,
            'user_agent': session.user_agent,
            'is_current': str(session.id) == current_sid,
            'last_seen': session.last_seen.isoformat() + 'Z',
            'created_at': session.created_at.isoformat() + 'Z',
            'expires_in': session.expires_in.isoformat() + 'Z',
        }
        for session in sessions
    ]
