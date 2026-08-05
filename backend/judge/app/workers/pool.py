"""Worker pool skeleton: N workers drain a queue of runs through the sandbox."""
import asyncio
import logging
from dataclasses import dataclass

from ..hub import EventHub
from ..languages import compile_source, get
from ..sandbox import RunLimits, Sandbox

logger = logging.getLogger(__name__)

HELLO_SOURCES = {
    "cpp": b'#include <iostream>\nint main() { std::cout << "hello from judge\\n"; }\n',
    "python": b'print("hello from judge")\n',
}

_DEMO_LIMITS = RunLimits(cpu_time_ms=2000, memory_kb=256 * 1024)
_OUTPUT_FILE = "out.txt"


@dataclass(frozen=True)
class DemoJob:
    id: str
    language_id: str


class WorkerPool:
    def __init__(self, sandbox: Sandbox, hub: EventHub, *, workers: int = 2) -> None:
        self._sandbox = sandbox
        self._hub = hub
        self._workers = workers
        self._queue: asyncio.Queue[DemoJob] = asyncio.Queue()
        self._tasks: list[asyncio.Task] = []

    async def start(self) -> None:
        self._tasks = [
            asyncio.create_task(self._worker(f"w{i}")) for i in range(self._workers)
        ]

    async def stop(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []

    async def submit(self, job: DemoJob) -> None:
        self._hub.publish({"type": "job.queued", "job_id": job.id, "language": job.language_id})
        self._queue.put_nowait(job)

    async def wait_idle(self) -> None:
        await self._queue.join()

    async def _worker(self, name: str) -> None:
        while True:
            job = await self._queue.get()
            self._hub.publish({"type": "job.started", "job_id": job.id, "worker": name})
            try:
                outcome = await self._run(job)
            except Exception as exc:
                # one broken job must not kill the worker
                logger.exception("demo job %s failed", job.id)
                outcome = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"}
            self._hub.publish(
                {"type": "job.finished", "job_id": job.id, "worker": name, **outcome}
            )
            self._queue.task_done()

    async def _run(self, job: DemoJob) -> dict:
        language = get(job.language_id)
        source = HELLO_SOURCES[job.language_id]
        async with self._sandbox.session() as session:
            compiled = await compile_source(session, language, source)
            if not compiled.ok:
                return {"status": "compile_error", "log": compiled.log[:500]}
            result = await session.run(
                language.run_argv, _DEMO_LIMITS, stdout=_OUTPUT_FILE
            )
            output = await session.read_file(_OUTPUT_FILE, max_bytes=1024)
        return {
            "status": result.status.value,
            "time_ms": result.cpu_time_ms,
            "memory_kb": result.memory_kb,
            "output": output.decode(errors="replace").strip(),
        }
