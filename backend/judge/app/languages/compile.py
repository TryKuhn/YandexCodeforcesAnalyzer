"""Compiling a submission inside the sandbox."""

from dataclasses import dataclass

from ..sandbox.base import SandboxSession
from ..sandbox.limits import RunLimits
from ..sandbox.result import RunStatus
from .registry import Language

_COMPILER_LOG = "compile.log"

# a compiler can produce endless template errors, enough to fill the disk
_MAX_LOG_BYTES = 64 * 1024


@dataclass(frozen=True)
class CompileResult:
    """Outcome of compiling one submission."""

    ok: bool
    log: str = ""
    # set when compilation itself broke rather than the code being invalid
    internal_error: bool = False

    @property
    def compile_error(self) -> bool:
        return not self.ok and not self.internal_error


async def compile_source(
    session: SandboxSession,
    language: Language,
    source: bytes,
    *,
    extra_files: dict[str, bytes] | None = None,
) -> CompileResult:
    """Put the source in the box and build it, returning the compiler log on failure."""
    await session.put_file(language.source_name, source)
    for name, data in (extra_files or {}).items():
        await session.put_file(name, data)

    if not language.needs_compilation:
        return CompileResult(ok=True)

    limits = RunLimits(
        cpu_time_ms=language.compile_time_ms,
        memory_kb=language.compile_memory_kb,
        max_processes=language.compile_processes,
    )
    assert language.compile_argv is not None
    result = await session.run(
        language.compile_argv,
        limits,
        stdout=_COMPILER_LOG,
        stderr=_COMPILER_LOG,
        # the compiler must write the binary, a submission run never may
        writable=True,
    )

    if result.status is RunStatus.OK:
        return CompileResult(ok=True)

    log = (await session.read_file(_COMPILER_LOG, max_bytes=_MAX_LOG_BYTES)).decode(
        errors="replace"
    )

    if result.status is RunStatus.INTERNAL_ERROR:
        return CompileResult(ok=False, log=log or result.message, internal_error=True)

    # hitting the compile limits is still the submission's fault, not ours
    if result.status is RunStatus.TIME_LIMIT:
        log = log or "compilation timed out"
    elif result.status is RunStatus.MEMORY_LIMIT:
        log = log or "compiler ran out of memory"

    return CompileResult(ok=False, log=log)
