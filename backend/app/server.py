import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text, select, delete, update
from sqlalchemy.exc import OperationalError

from api import health_router
from api.crypt import verify_token, get_current_user
from api.user import contest_router
from api.user.auth import auth_router
from api.user.codeforces import codeforces_router
from api.user.gpt import gpt_router
from api.user.plagiarism import plagiarism_router
from api.user.polygon.base_polygon import polygon_router
from api.user.yandex import yandex_router
from app.database import engine, Session
from app.logging_config import setup_logging, get_logger
from app.middlewares.log_middleware import LoggingMiddleware
from models import Role, RefreshToken
from settings import settings

LOG_LEVEL = logging.INFO
LOG_TO_STDOUT = True
LOG_TO_FILE = True

setup_logging(LOG_LEVEL, LOG_TO_FILE, LOG_TO_STDOUT)
logger = get_logger(__name__)


async def cleanup_expired_tokens():
    while True:
        try:
            async with Session() as db:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                stmt = delete(RefreshToken).where(RefreshToken.expires_in < now)
                await db.execute(stmt)
                await db.commit()
        except Exception as e:
            print(f"--- [CRON] Cleanup failed: {e} ---")

        await asyncio.sleep(86400)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info('=' * 60)
    logger.info('App startup complete.')
    logger.info('=' * 60)

    cleanup_task = asyncio.create_task(cleanup_expired_tokens())

    for _ in range(5):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                await conn.commit()

            async with Session() as db:
                result = await db.execute(select(Role).filter_by(name="User"))
                if not result.scalars().first():
                    db.add(Role(name="User"))
                    db.add(Role(name="Admin"))
                    await db.commit()

            break
        except (OperationalError, Exception) as e:
            await asyncio.sleep(2)

    yield

    cleanup_task.cancel()
    await engine.dispose()

    logger.info('=' * 60)
    logger.info('App shutdown complete.')
    logger.info('=' * 60)


app = FastAPI(lifespan=lifespan)

app.add_middleware(LoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware('http')
async def update_last_seen_middleware(request: Request, call_next):
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
        try:
            payload = verify_token(token)
            sid = payload.get("sid")
            if sid:
                async with Session() as db:
                    await db.execute(
                        update(RefreshToken)
                        .where(RefreshToken.id == sid)
                        .values(last_seen=datetime.now().replace(tzinfo=None))
                    )
                    await db.commit()
        except:
            pass

    return await call_next(request)


app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(contest_router, prefix="/api/contests", tags=["contest"], dependencies=[Depends(get_current_user)])
app.include_router(codeforces_router, prefix="/api/codeforces", tags=["codeforces"],
                   dependencies=[Depends(get_current_user)])
app.include_router(polygon_router, prefix="/api/polygon", tags=["polygon"], dependencies=[Depends(get_current_user)])
app.include_router(gpt_router, prefix="/api/ai", tags=["gpt"], dependencies=[Depends(get_current_user)])
app.include_router(yandex_router, prefix="/api/yandex", tags=["yandex"], dependencies=[Depends(get_current_user)])
app.include_router(plagiarism_router, prefix="/api/analytics", tags=["plagiarism"],
                   dependencies=[Depends(get_current_user)])
