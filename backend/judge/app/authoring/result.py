"""Outcome of building a problem."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class BuiltTest:
    index: int
    input_data: bytes
    answer_data: bytes
    group: str | None = None
    points: float = 0.0
    # how this test came to be, for the jury UI
    origin: str = "generated"


@dataclass
class BuildResult:
    """A self-contained package: tests with answers, plus the checker."""

    ok: bool
    tests: list[BuiltTest] = field(default_factory=list)
    checker: bytes = b""
    time_limit_ms: int = 1000
    memory_limit_mb: int = 256
    # what went wrong, aimed at the jury rather than a contestant
    error: str = ""
    failed_stage: str = ""
    log: str = ""

    @property
    def total_points(self) -> float:
        return round(sum(t.points for t in self.tests), 6)
