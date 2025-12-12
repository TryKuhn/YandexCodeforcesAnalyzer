from fastapi import Depends, APIRouter
from sqlalchemy.orm import Session

from backend.api.schemas import UserRegister, UserLogin, Token
from backend.app.database import get_db

router = APIRouter()


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.post("/register")
async def register(payload: UserRegister, db: Session = Depends(get_db)) -> dict:
    return {"message": "Welcome back!"}


@router.post("/login")
async def login(user: UserLogin, db: Session = Depends(get_db)) -> dict:
    return {"message": "Login successful!"}


@router.post("/logout")
async def logout(user: UserLogin, db: Session = Depends(get_db)) -> dict:
    return {"message": "Logout successful!"}


@router.post("/refresh")
async def refresh(user: Token, db: Session = Depends(get_db)) -> dict:
    return {"message": "Welcome back!"}


@router.post("/link_codeforces")
async def link_codeforces(user: Token, db: Session = Depends(get_db)) -> dict:
    return {"message": "Codeforces account linked!"}


@router.post("/link_yandex")
async def link_yandex(user: Token, db: Session = Depends(get_db)) -> dict:
    return {"message": "Yandex account linked!"}
