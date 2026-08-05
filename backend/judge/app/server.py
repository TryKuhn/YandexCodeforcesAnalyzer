"""Judge service API: health, demo run, live status stream."""
import base64
import logging
import os
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from .authoring import (GeneratedTest, LockBusy, ManualTest, ProblemBuilder,
                        ProblemSource)
from .engine import JudgingEngine, ProblemSpec, SubmissionSpec, TestCase
from .hub import EventHub
from .sandbox import BoxPool, IsolateSandbox
from .workers import DemoJob, WorkerPool

logging.basicConfig(level=logging.INFO)

WORKERS = int(os.environ.get("JUDGE_WORKERS", "2"))
BOXES = int(os.environ.get("JUDGE_BOXES", "8"))

_DEMO_LANGUAGES = ("cpp", "python")


class TestPayload(BaseModel):
    index: int
    # base64 so arbitrary bytes survive JSON
    input: str
    answer: str
    group: str | None = None
    points: float = 0.0


class JudgeRequest(BaseModel):
    source: str
    language: str = "cpp"
    checker: str
    tests: list[TestPayload] = Field(min_length=1)
    time_limit_ms: int = 1000
    memory_limit_mb: int = 256
    stop_on_first_failure: bool = True


class BuildTestPayload(BaseModel):
    # base64 for a manual test, generator arguments for a produced one
    input: str | None = None
    args: str | None = None
    group: str | None = None
    points: float = 0.0


class BuildRequest(BaseModel):
    name: str
    main_solution: str
    checker: str
    generator: str | None = None
    validator: str | None = None
    tests: list[BuildTestPayload] = Field(min_length=1)
    time_limit_ms: int = 1000
    memory_limit_mb: int = 256
    language: str = "cpp"


@asynccontextmanager
async def lifespan(app: FastAPI):
    sandbox = IsolateSandbox(BoxPool(size=BOXES))
    app.state.hub = EventHub()
    app.state.engine = JudgingEngine(sandbox)
    app.state.builder = ProblemBuilder(sandbox)
    app.state.pool = WorkerPool(sandbox, app.state.hub, workers=WORKERS)
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


@app.post("/judge")
async def judge_submission(request: JudgeRequest) -> dict:
    """Judge one submission; progress goes out on /ws/status."""
    run_id = uuid.uuid4().hex[:8]
    problem = ProblemSpec(
        tests=[
            TestCase(
                index=t.index,
                input_data=base64.b64decode(t.input),
                answer_data=base64.b64decode(t.answer),
                group=t.group,
                points=t.points,
            )
            for t in request.tests
        ],
        checker_source=request.checker.encode(),
        time_limit_ms=request.time_limit_ms,
        memory_limit_mb=request.memory_limit_mb,
        stop_on_first_failure=request.stop_on_first_failure,
    )
    submission = SubmissionSpec(source=request.source.encode(), language_id=request.language)

    hub = app.state.hub
    hub.publish({"type": "judge.started", "run_id": run_id, "tests": len(problem.tests)})

    async def progress(done: int, total: int) -> None:
        hub.publish({"type": "judge.progress", "run_id": run_id, "done": done, "total": total})

    result = await app.state.engine.judge(problem, submission, progress=progress)
    payload = {
        "run_id": run_id,
        "verdict": result.verdict.value,
        "score": result.score,
        "max_time_ms": result.max_time_ms,
        "max_memory_kb": result.max_memory_kb,
        "first_failed_test": result.first_failed_test,
        "compile_log": result.compile_log[:2000],
        "tests": [
            {
                "index": t.test_index,
                "verdict": t.verdict.value,
                "time_ms": t.time_ms,
                "memory_kb": t.memory_kb,
                "comment": t.comment,
            }
            for t in result.tests
        ],
    }
    hub.publish({"type": "judge.finished", "run_id": run_id, "verdict": payload["verdict"]})
    return payload


@app.post("/authoring/build")
async def build_problem(request: BuildRequest) -> dict:
    """Build a problem from jury sources: generate tests, validate, solve."""
    source = ProblemSource(
        name=request.name,
        main_solution=request.main_solution.encode(),
        checker=request.checker.encode(),
        generator=request.generator.encode() if request.generator else None,
        validator=request.validator.encode() if request.validator else None,
        manual_tests=[
            ManualTest(
                input_data=base64.b64decode(t.input),
                group=t.group,
                points=t.points,
            )
            for t in request.tests
            if t.input is not None
        ],
        generated_tests=[
            GeneratedTest(args=t.args, group=t.group, points=t.points)
            for t in request.tests
            if t.args is not None
        ],
        time_limit_ms=request.time_limit_ms,
        memory_limit_mb=request.memory_limit_mb,
        language_id=request.language,
    )

    hub = app.state.hub
    hub.publish({"type": "build.started", "problem": request.name})
    try:
        result = await app.state.builder.build(source)
    except LockBusy as exc:
        hub.publish({"type": "build.busy", "problem": request.name})
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    hub.publish(
        {"type": "build.finished", "problem": request.name, "ok": result.ok}
    )
    return {
        "ok": result.ok,
        "failed_stage": result.failed_stage,
        "error": result.error,
        "log": result.log[:2000],
        "total_points": result.total_points,
        "time_limit_ms": result.time_limit_ms,
        "memory_limit_mb": result.memory_limit_mb,
        "checker": result.checker.decode(errors="replace"),
        "tests": [
            {
                "index": t.index,
                "input": base64.b64encode(t.input_data).decode(),
                "answer": base64.b64encode(t.answer_data).decode(),
                "group": t.group,
                "points": t.points,
                "origin": t.origin,
            }
            for t in result.tests
        ],
    }


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
