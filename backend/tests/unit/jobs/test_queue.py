"""Job rows: enqueue and state transitions."""
from jobs import queue
from models.jobs.job import JobStatus


async def test_enqueue_persists_row_and_pushes_id(session_factory, transport):
    async with session_factory() as db:
        job = await queue.enqueue(db, transport, "demo", {"x": 1}, user_id=7)

    assert job.status == JobStatus.QUEUED.value
    assert job.payload == {"x": 1}
    assert job.user_id == 7
    assert transport.pushed == [str(job.id)]


async def test_claim_takes_a_queued_job_once(session_factory, transport):
    async with session_factory() as db:
        job = await queue.enqueue(db, transport, "demo", {})
        first = await queue.claim(db, job.id)
        second = await queue.claim(db, job.id)

    assert first is not None
    assert first.status == JobStatus.RUNNING.value
    assert first.attempts == 1
    # duplicate delivery must not run the job twice
    assert second is None


async def test_running_job_is_only_claimable_as_reclaim(session_factory, transport):
    async with session_factory() as db:
        job = await queue.enqueue(db, transport, "demo", {})
        await queue.claim(db, job.id)

        assert await queue.claim(db, job.id) is None
        reclaimed = await queue.claim(db, job.id, reclaim=True)

    assert reclaimed is not None
    assert reclaimed.attempts == 2


async def test_complete_stores_result(session_factory, transport):
    async with session_factory() as db:
        job = await queue.enqueue(db, transport, "demo", {})
        job = await queue.claim(db, job.id)
        await queue.complete(db, job, {"answer": 42})

    assert job.status == JobStatus.DONE.value
    assert job.progress == 100
    assert job.result == {"answer": 42}
    assert job.finished_at is not None


async def test_fail_below_max_requeues(session_factory, transport):
    async with session_factory() as db:
        job = await queue.enqueue(db, transport, "demo", {})
        job = await queue.claim(db, job.id)
        retry = await queue.fail(db, job, "boom", max_attempts=3)

    assert retry is True
    assert job.status == JobStatus.QUEUED.value
    assert job.error == "boom"


async def test_fail_at_max_is_permanent(session_factory, transport):
    async with session_factory() as db:
        job = await queue.enqueue(db, transport, "demo", {})
        for _ in range(3):
            claimed = await queue.claim(db, job.id)
            retry = await queue.fail(db, claimed, "boom", max_attempts=3)

    assert retry is False
    assert claimed.status == JobStatus.FAILED.value
    assert claimed.finished_at is not None


async def test_set_progress_clamps_to_percent_range(session_factory, transport):
    async with session_factory() as db:
        job = await queue.enqueue(db, transport, "demo", {})
        await queue.set_progress(db, job, 250)
        assert job.progress == 100
        await queue.set_progress(db, job, -5)
        assert job.progress == 0
