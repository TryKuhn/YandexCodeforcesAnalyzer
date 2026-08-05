"""Enqueueing and job-row state transitions."""
import uuid

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from models.jobs.job import Job, JobStatus, utcnow

from .transport import Transport


async def enqueue(
    db: AsyncSession,
    transport: Transport,
    job_type: str,
    payload: dict,
    *,
    user_id: int | None = None,
) -> Job:
    """Persist a job and wake a worker; commit first so a crash never loses it."""
    job = Job(type=job_type, payload=payload, user_id=user_id)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    await transport.push(str(job.id))
    return job


async def claim(db: AsyncSession, job_id: uuid.UUID, *, reclaim: bool = False) -> Job | None:
    """Atomically take a job, so duplicate deliveries are harmless.

    Reclaimed entries may also take RUNNING jobs — their worker is presumed dead.
    """
    allowed = [JobStatus.QUEUED.value]
    if reclaim:
        allowed.append(JobStatus.RUNNING.value)
    result = await db.execute(
        update(Job)
        .where(Job.id == job_id, Job.status.in_(allowed))
        .values(status=JobStatus.RUNNING.value, started_at=utcnow(), attempts=Job.attempts + 1)
        .returning(Job.id)
    )
    await db.commit()
    if result.first() is None:
        return None
    return await db.get(Job, job_id)


async def set_progress(db: AsyncSession, job: Job, percent: int) -> None:
    job.progress = max(0, min(100, percent))
    await db.commit()


async def complete(db: AsyncSession, job: Job, result: dict) -> None:
    job.status = JobStatus.DONE.value
    job.progress = 100
    job.result = result
    job.finished_at = utcnow()
    await db.commit()


async def fail(db: AsyncSession, job: Job, error: str, *, max_attempts: int) -> bool:
    """Record a failure; returns True when the job should be retried."""
    retry = job.attempts < max_attempts
    job.error = error
    job.status = JobStatus.QUEUED.value if retry else JobStatus.FAILED.value
    if not retry:
        job.finished_at = utcnow()
    await db.commit()
    return retry
