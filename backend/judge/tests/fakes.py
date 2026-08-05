"""In-memory sandbox for tests, so judging logic can be checked without isolate."""

from collections.abc import Mapping, Sequence
from contextlib import asynccontextmanager
from pathlib import Path

from app.sandbox.base import Sandbox, SandboxSession
from app.sandbox.limits import RunLimits
from app.sandbox.result import RunResult, RunStatus


class FakeSession(SandboxSession):
    """Records what was asked of it and replays canned results."""

    def __init__(self, results: Sequence[RunResult] | None = None) -> None:
        self.files: dict[str, bytes] = {}
        self.runs: list[dict[str, object]] = []
        self._results = list(results or [])

    @property
    def box_dir(self) -> Path:
        return Path("/fake/box")

    async def put_file(self, name: str, data: bytes, *, executable: bool = False) -> None:
        self.files[name] = data

    async def read_file(self, name: str, *, max_bytes: int | None = None) -> bytes:
        data = self.files.get(name, b"")
        return data if max_bytes is None else data[:max_bytes]

    async def run(
        self,
        argv: Sequence[str],
        limits: RunLimits,
        *,
        stdin: str | None = None,
        stdout: str | None = None,
        stderr: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> RunResult:
        self.runs.append(
            {
                "argv": list(argv),
                "limits": limits,
                "stdin": stdin,
                "stdout": stdout,
                "stderr": stderr,
            }
        )
        if self._results:
            return self._results.pop(0)
        return RunResult(status=RunStatus.OK)


class FakeSandbox(Sandbox):
    """Hands out FakeSessions; pass canned sessions to script specific runs."""

    def __init__(self, sessions: list[FakeSession] | None = None) -> None:
        self._sessions = list(sessions or [])
        self.opened = 0

    @asynccontextmanager
    async def session(self):
        self.opened += 1
        yield self._sessions.pop(0) if self._sessions else FakeSession()
