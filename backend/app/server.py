import time
from contextlib import asynccontextmanager
from logging import INFO, basicConfig
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy.exc import OperationalError

from api.user_api import router
from app.database import engine

log_dir = Path("app/logs")
log_dir.mkdir(parents=True, exist_ok=True)

basicConfig(
    filename=log_dir / "logs.txt",
    level=INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    for _ in range(5):
        try:
            with engine.connect():
                pass
            break
        except OperationalError:
            time.sleep(1)

    yield

    engine.dispose()


app = FastAPI(lifespan=lifespan)
app.include_router(router)
