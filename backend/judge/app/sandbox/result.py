"""Outcome of a sandboxed run."""

from dataclasses import dataclass
from enum import Enum


class RunStatus(str, Enum):
    """How the process ended, not a verdict: OK here can still be a wrong answer."""

    OK = "OK"
    RUNTIME_ERROR = "RE"
    TIME_LIMIT = "TL"
    MEMORY_LIMIT = "ML"
    OUTPUT_LIMIT = "OL"
    # the sandbox itself broke, never the contestant's fault
    INTERNAL_ERROR = "XX"


@dataclass(frozen=True)
class RunResult:
    """Measurements and exit state of one execution."""

    status: RunStatus
    exit_code: int = 0
    signal: int | None = None
    cpu_time_ms: int = 0
    wall_time_ms: int = 0
    memory_kb: int = 0
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status is RunStatus.OK

    def describe(self) -> str:
        """Short line for logs and jury UI."""
        base = f"{self.status.value} time={self.cpu_time_ms}ms mem={self.memory_kb}kb"
        if self.signal:
            base += f" signal={self.signal}"
        if self.message:
            base += f" ({self.message})"
        return base
