"""Resource limits for a sandboxed run."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RunLimits:
    """Limits for one execution, milliseconds and kilobytes everywhere."""

    cpu_time_ms: int
    memory_kb: int

    # a program that sleeps burns no CPU, so only this bounds it
    wall_time_ms: int = 0

    # grace period so a solution that just overshot gets measured, not guessed
    extra_time_ms: int = 500

    # 1 means no forking at all, which is what stops fork bombs
    max_processes: int = 1

    output_kb: int = 64 * 1024

    # 0 means "do not cap separately", deep recursion is normal here
    stack_kb: int = 0

    def __post_init__(self) -> None:
        if self.cpu_time_ms <= 0:
            raise ValueError("cpu_time_ms must be positive")
        if self.memory_kb <= 0:
            raise ValueError("memory_kb must be positive")
        if self.max_processes < 1:
            raise ValueError("max_processes must be at least 1")

    @property
    def effective_wall_time_ms(self) -> int:
        """Wall limit handed to the sandbox, double the CPU limit by default."""
        return self.wall_time_ms if self.wall_time_ms > 0 else self.cpu_time_ms * 2

    @classmethod
    def from_problem(
        cls,
        time_limit_ms: int,
        memory_limit_mb: int,
        *,
        tl_multiplier: float = 1.0,
        **overrides: int,
    ) -> "RunLimits":
        """Build limits from problem metadata, scaling time for slower languages."""
        return cls(
            cpu_time_ms=int(time_limit_ms * tl_multiplier),
            memory_kb=memory_limit_mb * 1024,
            **overrides,
        )
