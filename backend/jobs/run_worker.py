"""Standalone worker process: python -m jobs.run_worker"""
import asyncio
import logging

from redis.asyncio import Redis

from app.database import Session
from jobs.transport import RedisStreamTransport
from jobs.worker import Handler, Worker
from settings import settings

# job handlers land here as heavy operations move to jobs (YCA-110, YCA-111)
HANDLERS: dict[str, Handler] = {}


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    worker = Worker(RedisStreamTransport(redis), Session, handlers=HANDLERS)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
