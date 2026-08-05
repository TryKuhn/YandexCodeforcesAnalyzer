"""Builds a problem locally: generate tests, validate them, solve them."""
import logging
import shlex

from ..languages import compile_source, get
from ..sandbox import RunLimits, RunStatus, Sandbox, SandboxError, SandboxSession
from .lock import BuildLock, LocalBuildLock
from .result import BuildResult, BuiltTest
from .spec import ProblemSource

logger = logging.getLogger(__name__)

_GENERATOR = "generator"
_VALIDATOR = "validator"
_SOLUTION = "main"

_INPUT = "input.txt"
_ANSWER = "answer.txt"
_STDERR = "stage.err"

# jury code is trusted, so it gets room to work rather than contest limits
_JURY_LIMITS = RunLimits(cpu_time_ms=30_000, memory_kb=1024 * 1024, max_processes=8)
_MAX_MESSAGE = 2000


class ProblemBuilder:
    def __init__(self, sandbox: Sandbox, lock: BuildLock | None = None) -> None:
        self._sandbox = sandbox
        self._lock = lock or LocalBuildLock()

    async def build(self, source: ProblemSource) -> BuildResult:
        """Produce a self-contained package; one build per problem at a time."""
        async with self._lock.hold(source.name):
            try:
                return await self._build(source)
            except SandboxError as exc:
                return BuildResult(
                    ok=False, failed_stage="sandbox", error=str(exc),
                    checker=source.checker,
                )

    async def _build(self, source: ProblemSource) -> BuildResult:
        language = get(source.language_id)

        async with self._sandbox.session() as session:
            for label, code, binary in (
                ("main solution", source.main_solution, _SOLUTION),
                ("generator", source.generator, _GENERATOR),
                ("validator", source.validator, _VALIDATOR),
            ):
                if code is None:
                    continue
                compiled = await compile_source(session, language, code, binary_name=binary)
                if not compiled.ok:
                    return BuildResult(
                        ok=False,
                        failed_stage=f"compile {label}",
                        error=f"{label} does not compile",
                        log=compiled.log[:_MAX_MESSAGE],
                        checker=source.checker,
                    )

            tests: list[BuiltTest] = []
            index = 0

            for manual in source.manual_tests:
                index += 1
                built = await self._finish_test(
                    session, language, index, manual.input_data,
                    manual.group, manual.points, "manual", source,
                )
                if isinstance(built, BuildResult):
                    return built
                tests.append(built)

            for planned in source.generated_tests:
                index += 1
                produced = await self._generate(session, language, planned.args)
                if isinstance(produced, BuildResult):
                    return produced
                built = await self._finish_test(
                    session, language, index, produced,
                    planned.group, planned.points, f"generated: {planned.args}", source,
                )
                if isinstance(built, BuildResult):
                    return built
                tests.append(built)

        if not tests:
            return BuildResult(
                ok=False, failed_stage="tests", error="the problem has no tests",
                checker=source.checker,
            )

        return BuildResult(
            ok=True,
            tests=tests,
            checker=source.checker,
            time_limit_ms=source.time_limit_ms,
            memory_limit_mb=source.memory_limit_mb,
        )

    async def _generate(self, session, language, args: str) -> bytes | BuildResult:
        run = await session.run(
            (*self._run_argv(language, _GENERATOR), *shlex.split(args)),
            _JURY_LIMITS,
            stdout=_INPUT,
            stderr=_STDERR,
        )
        if run.status is not RunStatus.OK:
            return BuildResult(
                ok=False,
                failed_stage="generator",
                error=f"generator failed on '{args}': {run.status.value}",
                log=await self._read_log(session),
            )
        return await session.read_file(_INPUT)

    async def _finish_test(
        self, session, language, index, input_data, group, points, origin, source,
    ) -> BuiltTest | BuildResult:
        """Validate one input, then solve it with the jury solution."""
        await session.put_file(_INPUT, input_data)

        if source.validator is not None:
            check = await session.run(
                self._run_argv(language, _VALIDATOR),
                _JURY_LIMITS,
                stdin=_INPUT,
                stderr=_STDERR,
            )
            if check.status is not RunStatus.OK:
                # an invalid test must never reach contestants
                return BuildResult(
                    ok=False,
                    failed_stage="validator",
                    error=f"test {index} ({origin}) is invalid",
                    log=await self._read_log(session),
                )

        solve = await session.run(
            self._run_argv(language, _SOLUTION),
            _JURY_LIMITS,
            stdin=_INPUT,
            stdout=_ANSWER,
            stderr=_STDERR,
        )
        if solve.status is not RunStatus.OK:
            return BuildResult(
                ok=False,
                failed_stage="main solution",
                error=f"main solution failed on test {index} ({origin}): {solve.status.value}",
                log=await self._read_log(session),
            )

        return BuiltTest(
            index=index,
            input_data=input_data,
            answer_data=await session.read_file(_ANSWER),
            group=group,
            points=points,
            origin=origin,
        )

    def _run_argv(self, language, binary: str) -> tuple[str, ...]:
        """Run command for one of the jury binaries built in this box."""
        return language.run_command(language.source_file(binary), binary)

    async def _read_log(self, session: SandboxSession) -> str:
        raw = await session.read_file(_STDERR, max_bytes=_MAX_MESSAGE)
        return raw.decode(errors="replace").strip()
