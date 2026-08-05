"""Hunting for a test where a candidate solution disagrees with the jury one."""
import logging
from collections.abc import Awaitable, Callable

from ..engine.checker import CHECKER_BINARY, run_checker
from ..engine.verdict import Verdict, from_run_status
from ..languages import compile_source, get
from ..sandbox import RunLimits, RunStatus, Sandbox, SandboxError
from .result import Counterexample, StressResult

logger = logging.getLogger(__name__)

_CANDIDATE = "candidate"
_REFERENCE = "reference"
_GENERATOR = "generator"

_INPUT = "input.txt"
_EXPECTED = "expected.txt"
_ACTUAL = "actual.txt"
_STDERR = "stage.err"

# jury code is trusted; the candidate runs under the problem's own limits
_JURY_LIMITS = RunLimits(cpu_time_ms=30_000, memory_kb=1024 * 1024, max_processes=8)
_MAX_OUTPUT = 8 * 1024

# progress(done, total)
ProgressHook = Callable[[int, int], Awaitable[None]]


class StressTester:
    def __init__(self, sandbox: Sandbox) -> None:
        self._sandbox = sandbox

    async def hunt(
        self,
        *,
        candidate: bytes,
        reference: bytes,
        generator: bytes,
        checker: bytes,
        gen_args: str = "{seed}",
        iterations: int = 50,
        time_limit_ms: int = 1000,
        memory_limit_mb: int = 256,
        language_id: str = "cpp",
        progress: ProgressHook | None = None,
    ) -> StressResult:
        """Run random tests until the candidate breaks or the budget runs out."""
        try:
            return await self._hunt(
                candidate, reference, generator, checker, gen_args, iterations,
                time_limit_ms, memory_limit_mb, language_id, progress,
            )
        except SandboxError as exc:
            return StressResult(found=False, failed_stage="sandbox", error=str(exc))

    async def _hunt(
        self,
        candidate: bytes,
        reference: bytes,
        generator: bytes,
        checker: bytes,
        gen_args: str,
        iterations: int,
        time_limit_ms: int,
        memory_limit_mb: int,
        language_id: str,
        progress: ProgressHook | None,
    ) -> StressResult:
        language = get(language_id)
        limits = RunLimits.from_problem(
            time_limit_ms, memory_limit_mb, tl_multiplier=language.tl_multiplier
        )

        async with self._sandbox.session() as session:
            for label, code, binary in (
                ("candidate", candidate, _CANDIDATE),
                ("reference", reference, _REFERENCE),
                ("generator", generator, _GENERATOR),
            ):
                compiled = await compile_source(session, language, code, binary_name=binary)
                if not compiled.ok:
                    return StressResult(
                        found=False,
                        failed_stage=f"compile {label}",
                        error=f"{label} does not compile: {compiled.log[:500]}",
                    )

            checker_build = await compile_source(
                session, get("cpp"), checker, binary_name=CHECKER_BINARY
            )
            if not checker_build.ok:
                return StressResult(
                    found=False,
                    failed_stage="compile checker",
                    error=f"checker does not compile: {checker_build.log[:500]}",
                )

            gen_argv = self._argv(language, _GENERATOR)
            candidate_argv = self._argv(language, _CANDIDATE)
            reference_argv = self._argv(language, _REFERENCE)

            for seed in range(1, iterations + 1):
                args = gen_args.format(seed=seed).split()
                made = await session.run(
                    (*gen_argv, *args), _JURY_LIMITS, stdout=_INPUT, stderr=_STDERR
                )
                if made.status is not RunStatus.OK:
                    return StressResult(
                        found=False,
                        iterations=seed - 1,
                        failed_stage="generator",
                        error=f"generator failed on seed {seed}",
                    )
                test_input = await session.read_file(_INPUT)

                jury = await session.run(
                    reference_argv, _JURY_LIMITS, stdin=_INPUT, stdout=_EXPECTED
                )
                if jury.status is not RunStatus.OK:
                    return StressResult(
                        found=False,
                        iterations=seed - 1,
                        failed_stage="reference",
                        error=f"the jury solution failed on seed {seed}",
                    )

                run = await session.run(
                    candidate_argv, limits, stdin=_INPUT, stdout=_ACTUAL
                )
                crashed = from_run_status(run.status)
                if crashed is not None and crashed is not Verdict.INTERNAL_ERROR:
                    return StressResult(
                        found=True,
                        iterations=seed,
                        counterexample=await self._snapshot(
                            session, seed, test_input, crashed.value
                        ),
                    )

                outcome = await run_checker(
                    session, input_name=_INPUT, output_name=_ACTUAL, answer_name=_EXPECTED
                )
                if outcome.verdict is Verdict.INTERNAL_ERROR:
                    return StressResult(
                        found=False,
                        iterations=seed - 1,
                        failed_stage="checker",
                        error=outcome.comment or "the checker broke",
                    )
                if outcome.verdict is not Verdict.OK:
                    reason = f"{outcome.verdict.value}: {outcome.comment}".strip(": ")
                    return StressResult(
                        found=True,
                        iterations=seed,
                        counterexample=await self._snapshot(
                            session, seed, test_input, reason
                        ),
                    )

                if progress:
                    await progress(seed, iterations)

        return StressResult(found=False, iterations=iterations)

    def _argv(self, language, binary: str) -> tuple[str, ...]:
        return language.run_command(language.source_file(binary), binary)

    async def _snapshot(self, session, seed, test_input, reason) -> Counterexample:
        return Counterexample(
            seed=seed,
            input_data=test_input[:_MAX_OUTPUT],
            expected=(await session.read_file(_EXPECTED, max_bytes=_MAX_OUTPUT)),
            actual=(await session.read_file(_ACTUAL, max_bytes=_MAX_OUTPUT)),
            reason=reason,
        )
