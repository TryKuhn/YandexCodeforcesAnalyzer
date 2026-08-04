"""Sandbox abstraction, so judging logic never talks to isolate directly."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from pathlib import Path

from .limits import RunLimits
from .result import RunResult


class SandboxError(RuntimeError):
    """The sandbox itself failed, so the submission must be retried, not rejected."""


class SandboxSession(ABC):
    """One isolated box, ready to receive files and run a program."""

    @property
    @abstractmethod
    def box_dir(self) -> Path:
        """Directory the sandboxed program sees as its working dir."""

    @abstractmethod
    async def put_file(self, name: str, data: bytes, *, executable: bool = False) -> None:
        """Place a file inside the box."""

    @abstractmethod
    async def read_file(self, name: str, *, max_bytes: int | None = None) -> bytes:
        """Read a file the program produced, capped so a huge output cannot blow up the worker."""

    @abstractmethod
    async def run(
        self,
        argv: Sequence[str],
        limits: RunLimits,
        *,
        stdin: str | None = None,
        stdout: str | None = None,
        stderr: str | None = None,
        env: Mapping[str, str] | None = None,
        writable: bool = False,
    ) -> RunResult:
        """Execute a program inside the box, stdio names are relative to it."""


class Sandbox(ABC):
    """Factory of sandbox sessions."""

    @asynccontextmanager
    @abstractmethod
    async def session(self) -> AsyncIterator[SandboxSession]:
        """Acquire a box, yield a session, always clean up afterwards."""
        raise NotImplementedError
        yield  # pragma: no cover
