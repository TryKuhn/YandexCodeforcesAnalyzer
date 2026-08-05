"""Standalone worker process: python -m jobs.run_worker"""
import asyncio
import logging

from redis.asyncio import Redis

from api.judge.grading import JOB_TYPE as JUDGE_JOB
from api.judge.grading import make_handler as make_judge_handler
from app.database import Session
from blobs import BlobStore
from jobs.transport import RedisStreamTransport
from jobs.worker import Handler, Worker
from settings import settings


def build_handlers() -> dict[str, Handler]:
    """Job types this worker knows how to run."""
    return {JUDGE_JOB: make_judge_handler(Session, BlobStore())}


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    worker = Worker(RedisStreamTransport(redis), Session, handlers=build_handlers())
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
