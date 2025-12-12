import time
from contextlib import asynccontextmanager
from logging import basicConfig, INFO

from fastapi import FastAPI

from sqlalchemy.exc import OperationalError

from backend.models.base import Base
from backend.api.user_api import router
from settings import ANALYZER_ROOT

from backend.app.database import engine



basicConfig(
    filename=ANALYZER_ROOT/"logs.txt",
    level=INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    for _ in range(5):
        try:
            with engine.connect() as conn:
                pass
            break
        except OperationalError:
            time.sleep(1)

    Base.metadata.create_all(engine)

    yield

    engine.dispose()

app = FastAPI(lifespan=lifespan)
app.include_router(router)
