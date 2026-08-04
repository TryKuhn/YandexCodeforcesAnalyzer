"""Compiling a submission inside the sandbox."""

from dataclasses import dataclass

from ..sandbox.base import SandboxSession
from ..sandbox.limits import RunLimits
from ..sandbox.result import RunStatus
from .registry import DEFAULT_BINARY, Language

# a compiler can produce endless template errors, enough to fill the disk
_MAX_LOG_BYTES = 64 * 1024


@dataclass(frozen=True)
class CompileResult:
    """Outcome of compiling one submission."""

    ok: bool
    log: str = ""
    # set when compilation itself broke rather than the code being invalid
    internal_error: bool = False
    source_name: str = ""
    binary_name: str = DEFAULT_BINARY

    @property
    def compile_error(self) -> bool:
        return not self.ok and not self.internal_error


async def compile_source(
    session: SandboxSession,
    language: Language,
    source: bytes,
    *,
    extra_files: dict[str, bytes] | None = None,
    binary_name: str = DEFAULT_BINARY,
) -> CompileResult:
    """Put the source in the box and build it, returning the compiler log on failure."""
    source_name = language.source_file(binary_name)
    log_name = "compile.log" if binary_name == DEFAULT_BINARY else f"compile_{binary_name}.log"

    await session.put_file(source_name, source)
    for name, data in (extra_files or {}).items():
        await session.put_file(name, data)

    if not language.needs_compilation:
        return CompileResult(ok=True, source_name=source_name, binary_name=binary_name)

    limits = RunLimits(
        cpu_time_ms=language.compile_time_ms,
        memory_kb=language.compile_memory_kb,
        max_processes=language.compile_processes,
    )
    result = await session.run(
        language.compile_command(source_name, binary_name),
        limits,
        stdout=log_name,
        stderr=log_name,
        # the compiler must write the binary, a submission run never may
        writable=True,
    )

    if result.status is RunStatus.OK:
        return CompileResult(ok=True, source_name=source_name, binary_name=binary_name)

    log = (await session.read_file(log_name, max_bytes=_MAX_LOG_BYTES)).decode(errors="replace")

    if result.status is RunStatus.INTERNAL_ERROR:
        return CompileResult(
            ok=False,
            log=log or result.message,
            internal_error=True,
            source_name=source_name,
            binary_name=binary_name,
        )

    # hitting the compile limits is still the submission's fault, not ours
    if result.status is RunStatus.TIME_LIMIT:
        log = log or "compilation timed out"
    elif result.status is RunStatus.MEMORY_LIMIT:
        log = log or "compiler ran out of memory"

    return CompileResult(ok=False, log=log, source_name=source_name, binary_name=binary_name)
