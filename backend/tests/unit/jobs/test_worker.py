"""Worker loop: dispatch, retries, recovery."""
import uuid

from jobs.worker import Worker
from jobs import queue
from models.jobs.job import Job, JobStatus


async def _get(session_factory, job_id) -> Job:
    async with session_factory() as db:
        return await db.get(Job, job_id)


async def test_happy_path(session_factory, transport):
    async def handler(payload, progress):
        return {"doubled": payload["x"] * 2}

    worker = Worker(transport, session_factory, handlers={"demo": handler})
    async with session_factory() as db:
        job = await queue.enqueue(db, transport, "demo", {"x": 21})

    processed = await worker.run_once(block_ms=0)

    assert processed == 1
    saved = await _get(session_factory, job.id)
    assert saved.status == JobStatus.DONE.value
    assert saved.result == {"doubled": 42}
    assert transport.acked == ["e1"]


async def test_progress_is_persisted(session_factory, transport):
    async def handler(payload, progress):
        await progress(60)
        raise RuntimeError("stop here so progress is the last write")

    worker = Worker(transport, session_factory, handlers={"demo": handler}, max_attempts=1)
    async with session_factory() as db:
        job = await queue.enqueue(db, transport, "demo", {})

    await worker.run_once(block_ms=0)

    saved = await _get(session_factory, job.id)
    assert saved.progress == 60


async def test_failure_retries_then_gives_up(session_factory, transport):
    attempts = []

    async def handler(payload, progress):
        attempts.append(1)
        raise ValueError("always broken")

    worker = Worker(transport, session_factory, handlers={"demo": handler}, max_attempts=2)
    async with session_factory() as db:
        job = await queue.enqueue(db, transport, "demo", {})

    # first run fails and re-pushes, second run fails permanently
    await worker.run_once(block_ms=0)
    await worker.run_once(block_ms=0)

    saved = await _get(session_factory, job.id)
    assert len(attempts) == 2
    assert saved.status == JobStatus.FAILED.value
    assert "always broken" in saved.error


async def test_unknown_job_type_fails_without_retry(session_factory, transport):
    worker = Worker(transport, session_factory, handlers={})
    async with session_factory() as db:
        job = await queue.enqueue(db, transport, "mystery", {})

    await worker.run_once(block_ms=0)

    saved = await _get(session_factory, job.id)
    assert saved.status == JobStatus.FAILED.value
    assert "no handler" in saved.error
    # nothing was re-pushed: a handler will not appear by itself
    assert transport.entries == []


async def test_duplicate_delivery_is_acked_and_skipped(session_factory, transport):
    runs = []

    async def handler(payload, progress):
        runs.append(1)
        return {}

    worker = Worker(transport, session_factory, handlers={"demo": handler})
    async with session_factory() as db:
        job = await queue.enqueue(db, transport, "demo", {})
    # the same job id delivered twice
    await transport.push(str(job.id))

    await worker.run_once(block_ms=0)

    assert len(runs) == 1
    assert len(transport.acked) == 2


async def test_reclaimed_entry_reruns_abandoned_job(session_factory, transport):
    async def handler(payload, progress):
        return {"ok": True}

    worker = Worker(transport, session_factory, handlers={"demo": handler})
    async with session_factory() as db:
        job = await queue.enqueue(db, transport, "demo", {})
        # a worker died mid-job: row is RUNNING, entry never acked
        await queue.claim(db, job.id)
    transport.entries.clear()
    transport.reclaimable.append(("stale1", str(job.id)))

    await worker.run_once(block_ms=0)

    saved = await _get(session_factory, job.id)
    assert saved.status == JobStatus.DONE.value
    assert saved.attempts == 2
    assert "stale1" in transport.acked


async def test_registering_same_type_twice_is_rejected(session_factory, transport):
    async def handler(payload, progress):
        return {}

    worker = Worker(transport, session_factory, handlers={"demo": handler})
    try:
        worker.register("demo", handler)
        raised = False
    except ValueError:
        raised = True
    assert raised


async def test_claim_of_missing_job_acks_quietly(session_factory, transport):
    worker = Worker(transport, session_factory, handlers={})
    await transport.push(str(uuid.uuid4()))

    await worker.run_once(block_ms=0)

    assert len(transport.acked) == 1
