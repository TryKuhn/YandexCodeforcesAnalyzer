"""Worker pool: events, concurrency, survival on failures."""
import asyncio

from app.hub import EventHub
from app.sandbox.result import RunResult, RunStatus
from app.workers import DemoJob, WorkerPool

from .fakes import FakeSandbox, FakeSession


def _drain(queue: asyncio.Queue) -> list[dict]:
    events = []
    while queue.qsize():
        events.append(queue.get_nowait())
    return events


async def _run_pool(pool: WorkerPool, jobs: list[DemoJob]) -> None:
    await pool.start()
    for job in jobs:
        await pool.submit(job)
    await asyncio.wait_for(pool.wait_idle(), timeout=5)
    await pool.stop()


async def test_happy_path_emits_full_event_chain():
    session = FakeSession([RunResult(status=RunStatus.OK), RunResult(status=RunStatus.OK, cpu_time_ms=7)])
    session.files["out.txt"] = b"hello from judge\n"
    hub = EventHub()
    queue = hub.subscribe()
    pool = WorkerPool(FakeSandbox([session]), hub, workers=1)

    await _run_pool(pool, [DemoJob(id="j1", language_id="cpp")])

    kinds = [e["type"] for e in _drain(queue)]
    assert kinds == ["job.queued", "job.started", "job.finished"]


async def test_finished_event_carries_run_outcome():
    session = FakeSession([RunResult(status=RunStatus.OK), RunResult(status=RunStatus.OK, cpu_time_ms=7, memory_kb=900)])
    session.files["out.txt"] = b"hello from judge\n"
    hub = EventHub()
    queue = hub.subscribe()
    pool = WorkerPool(FakeSandbox([session]), hub, workers=1)

    await _run_pool(pool, [DemoJob(id="j1", language_id="cpp")])

    finished = _drain(queue)[-1]
    assert finished["status"] == "OK"
    assert finished["output"] == "hello from judge"
    assert finished["time_ms"] == 7


async def test_compile_error_is_reported_not_raised():
    session = FakeSession([RunResult(status=RunStatus.RUNTIME_ERROR, exit_code=1)])
    session.files["compile.log"] = b"main.cpp:1: error"
    hub = EventHub()
    queue = hub.subscribe()
    pool = WorkerPool(FakeSandbox([session]), hub, workers=1)

    await _run_pool(pool, [DemoJob(id="j1", language_id="cpp")])

    finished = _drain(queue)[-1]
    assert finished["status"] == "compile_error"
    assert "error" in finished["log"]


async def test_broken_sandbox_does_not_kill_the_worker():
    class ExplodingSandbox(FakeSandbox):
        def session(self):
            raise RuntimeError("isolate is gone")

    hub = EventHub()
    queue = hub.subscribe()
    pool = WorkerPool(ExplodingSandbox(), hub, workers=1)

    await _run_pool(
        pool,
        [DemoJob(id="dead", language_id="cpp"), DemoJob(id="alive", language_id="python")],
    )

    finished = [e for e in _drain(queue) if e["type"] == "job.finished"]
    # both jobs got a verdict event even though the sandbox exploded
    assert [e["job_id"] for e in finished] == ["dead", "alive"]
    assert all(e["status"] == "failed" for e in finished)


async def test_jobs_spread_across_workers():
    sandbox = FakeSandbox()
    hub = EventHub()
    queue = hub.subscribe()
    pool = WorkerPool(sandbox, hub, workers=3)

    jobs = [DemoJob(id=f"j{i}", language_id="python") for i in range(6)]
    await _run_pool(pool, jobs)

    finished = [e for e in _drain(queue) if e["type"] == "job.finished"]
    assert len(finished) == 6
    assert sandbox.opened == 6
