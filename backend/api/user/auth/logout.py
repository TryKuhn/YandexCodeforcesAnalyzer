from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.crypt import hash_password, get_current_user
from api.pydantic_schemas import Token, Authorization
from app.database import get_db
from models import RefreshToken

router = APIRouter()

@router.post('/logout')
async def logout(payload: Token, db: Session = Depends(get_db)) -> dict:
    db_token = db.query(RefreshToken).filter_by(refresh_hash=hash_password(payload.refresh_token)).first()
    if not db_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Invalid refresh token.'
        )

    db.delete(db_token)
    db.commit()

    return {'message': 'Successfully logged out.'}


@router.post('/logout_all')
async def logout_all(payload: Authorization, db: Session = Depends(get_db)) -> dict:
    user_id = get_current_user(payload.Authorization)

    db.query(RefreshToken).filter(RefreshToken.user_id == user_id).delete()
    db.commit()

    return {'message': 'Successfully logged all.'}
