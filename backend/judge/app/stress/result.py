"""Outcome of hunting for a counterexample."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Counterexample:
    """The test that broke the candidate, with both answers side by side."""

    seed: int
    input_data: bytes
    expected: bytes
    actual: bytes
    # why it counts as a break: a checker verdict, or how the run died
    reason: str


@dataclass
class StressResult:
    found: bool
    iterations: int = 0
    counterexample: Counterexample | None = None
    # set when the hunt could not run at all (compile error, broken jury code)
    error: str = ""
    failed_stage: str = ""

    @property
    def ok(self) -> bool:
        """True when the search ran and the candidate survived it."""
        return not self.error and not self.found
