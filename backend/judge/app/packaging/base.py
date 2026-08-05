"""Package interchange: one plugin per external format, Polygon is just one of them."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class PackageTest:
    index: int
    input_data: bytes
    answer_data: bytes
    group: str | None = None
    points: float = 0.0
    # samples are shown in the statement, so they must survive a round trip
    is_sample: bool = False


@dataclass
class Package:
    """A problem that can stand on its own: tests with answers plus a checker."""

    name: str
    tests: list[PackageTest] = field(default_factory=list)
    checker: bytes = b""
    time_limit_ms: int = 1000
    memory_limit_mb: int = 256
    files: dict[str, bytes] = field(default_factory=dict)


class PackageFormat(ABC):
    """Reads and writes one archive layout."""

    name: str

    @abstractmethod
    def export(self, package: Package) -> bytes:
        """Serialise the package into an archive."""

    @abstractmethod
    def materialize(self, archive: bytes) -> Package:
        """Read an archive back into a package."""


class PackageError(ValueError):
    """The archive is not what this format expects."""
