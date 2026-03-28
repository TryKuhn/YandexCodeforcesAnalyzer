from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.crypt import get_current_user, hash_password, verify_password
from api.pydantic_schemas import ChangePassword, Token
from app.database import get_db
from models import RefreshToken, User

router = APIRouter()

@router.post('/change_password')
async def change_password(payload: ChangePassword, token: Token, db: Session = Depends(get_db)) -> dict:
    user_id = get_current_user(token.access_token)

    refresh_hash = hash_password(token.refresh_token)

    db_token = db.query(RefreshToken).filter_by(refresh_hash=refresh_hash).first()
    if not db_token or db_token.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )

    user = db.query(User).filter_by(id=user_id).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='User not found.'
        )

    if not verify_password(payload.old_password, user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Invalid password.'
        )

    if payload.old_password == payload.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='New password can\'t be the same.'
        )

    if payload.new_password != payload.validate_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='New password and confirmation do not match.'
        )

    user.password = hash_password(payload.new_password)

    (db.query(RefreshToken).
     filter(RefreshToken.user_id == user.id, RefreshToken.refresh_hash != hash_password(token.refresh_token))
     .delete())

    db.commit()

    return {'message': 'Successfully changed password.'}