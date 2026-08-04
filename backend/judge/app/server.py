"""Judge service API: health, demo run, live status stream."""
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from .hub import EventHub
from .sandbox import BoxPool, IsolateSandbox
from .workers import DemoJob, WorkerPool

WORKERS = int(os.environ.get("JUDGE_WORKERS", "2"))
BOXES = int(os.environ.get("JUDGE_BOXES", "8"))

_DEMO_LANGUAGES = ("cpp", "python")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.hub = EventHub()
    app.state.pool = WorkerPool(
        IsolateSandbox(BoxPool(size=BOXES)), app.state.hub, workers=WORKERS
    )
    await app.state.pool.start()
    yield
    await app.state.pool.stop()


app = FastAPI(title="judge", lifespan=lifespan)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/demo/hello-world")
async def demo_hello_world(count: int = 2) -> dict:
    """Queue a few hello-world runs, watch them on /ws/status."""
    count = max(1, min(count, 50))
    jobs = [
        DemoJob(id=uuid.uuid4().hex[:8], language_id=_DEMO_LANGUAGES[i % 2])
        for i in range(count)
    ]
    for job in jobs:
        await app.state.pool.submit(job)
    return {"jobs": [job.id for job in jobs]}


@app.websocket("/ws/status")
async def status_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    queue = websocket.app.state.hub.subscribe()
    try:
        while True:
            await websocket.send_json(await queue.get())
    except WebSocketDisconnect:
        pass
    finally:
        websocket.app.state.hub.unsubscribe(queue)
