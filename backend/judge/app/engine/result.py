"""Judging results: one per test, plus the aggregate."""
from dataclasses import dataclass, field

from .verdict import Verdict


@dataclass(frozen=True)
class TestResult:
    test_index: int
    verdict: Verdict
    time_ms: int = 0
    memory_kb: int = 0
    comment: str = ""
    points_ratio: float | None = None


@dataclass
class JudgeResult:
    verdict: Verdict
    score: float = 0.0
    tests: list[TestResult] = field(default_factory=list)
    compile_log: str = ""

    @property
    def max_time_ms(self) -> int:
        return max((t.time_ms for t in self.tests), default=0)

    @property
    def max_memory_kb(self) -> int:
        return max((t.memory_kb for t in self.tests), default=0)

    @property
    def first_failed_test(self) -> int | None:
        for test in self.tests:
            if test.verdict is not Verdict.OK:
                return test.test_index
        return None
