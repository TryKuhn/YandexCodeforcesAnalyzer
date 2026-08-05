"""What it takes to build a problem locally, without Polygon."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class GeneratedTest:
    """One line of the test script: the generator plus its arguments."""

    args: str
    group: str | None = None
    points: float = 0.0


@dataclass(frozen=True)
class ManualTest:
    """A test written by hand, usually a sample from the statement."""

    input_data: bytes
    group: str | None = None
    points: float = 0.0


@dataclass(frozen=True)
class ProblemSource:
    """Everything the jury wrote; tests and answers are derived from it."""

    name: str
    main_solution: bytes
    checker: bytes

    generator: bytes | None = None
    validator: bytes | None = None

    manual_tests: list[ManualTest] = field(default_factory=list)
    generated_tests: list[GeneratedTest] = field(default_factory=list)

    time_limit_ms: int = 1000
    memory_limit_mb: int = 256
    language_id: str = "cpp"
