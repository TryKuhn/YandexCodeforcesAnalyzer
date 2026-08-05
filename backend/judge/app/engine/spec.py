"""What the engine needs to judge: the problem, its tests, and one submission."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TestCase:
    index: int
    input_data: bytes
    answer_data: bytes
    # IOI-style grouping; None means the test stands alone
    group: str | None = None
    points: float = 0.0


@dataclass(frozen=True)
class ProblemSpec:
    tests: list[TestCase]
    checker_source: bytes
    time_limit_ms: int = 1000
    memory_limit_mb: int = 256
    # stop at the first failure (ICPC); IOI needs every group scored
    stop_on_first_failure: bool = True
    checker_language_id: str = "cpp"


@dataclass(frozen=True)
class SubmissionSpec:
    source: bytes
    language_id: str
    files: dict[str, bytes] = field(default_factory=dict)
