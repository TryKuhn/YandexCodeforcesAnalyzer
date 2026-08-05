"""The judging engine: compile, run every test, check, aggregate."""
import logging
from collections.abc import Awaitable, Callable

from ..languages import compile_source, get
from ..sandbox import RunLimits, Sandbox, SandboxError, SandboxSession
from .checker import CHECKER_BINARY, run_checker
from .result import JudgeResult, TestResult
from .scoring import score_tests
from .spec import ProblemSpec, SubmissionSpec
from .verdict import Verdict, from_run_status

logger = logging.getLogger(__name__)

_INPUT = "input.txt"
_OUTPUT = "output.txt"
_ANSWER = "answer.txt"

# progress(done, total)
ProgressHook = Callable[[int, int], Awaitable[None]]


class JudgingEngine:
    def __init__(self, sandbox: Sandbox) -> None:
        self._sandbox = sandbox

    async def judge(
        self,
        problem: ProblemSpec,
        submission: SubmissionSpec,
        *,
        progress: ProgressHook | None = None,
    ) -> JudgeResult:
        language = get(submission.language_id)
        limits = RunLimits.from_problem(
            problem.time_limit_ms,
            problem.memory_limit_mb,
            tl_multiplier=language.tl_multiplier,
        )

        try:
            return await self._judge_in_sandbox(problem, submission, language, limits, progress)
        except SandboxError as exc:
            # the judge is broken, not the submission
            logger.error("sandbox unavailable: %s", exc)
            return JudgeResult(verdict=Verdict.INTERNAL_ERROR, compile_log=str(exc))

    async def _judge_in_sandbox(
        self, problem, submission, language, limits, progress
    ) -> JudgeResult:
        async with self._sandbox.session() as session:
            compiled = await compile_source(
                session, language, submission.source, extra_files=submission.files
            )
            if not compiled.ok:
                verdict = (
                    Verdict.INTERNAL_ERROR if compiled.internal_error else Verdict.COMPILE_ERROR
                )
                return JudgeResult(verdict=verdict, compile_log=compiled.log)

            checker_ready = await self._build_checker(session, problem)
            if not checker_ready:
                return JudgeResult(
                    verdict=Verdict.INTERNAL_ERROR, compile_log="checker failed to compile"
                )

            run_argv = language.run_command(compiled.source_name, compiled.binary_name)
            results: list[TestResult] = []
            total = len(problem.tests)
            for done, test in enumerate(problem.tests, start=1):
                result = await self._run_test(session, run_argv, limits, test)
                results.append(result)
                if progress:
                    await progress(done, total)
                if result.verdict is not Verdict.OK and problem.stop_on_first_failure:
                    break

        return self._aggregate(problem, results)

    async def _build_checker(self, session: SandboxSession, problem: ProblemSpec) -> bool:
        checker_language = get(problem.checker_language_id)
        # the checker is ours, so it compiles under its own name, not the solution's
        compiled = await compile_source(
            session, checker_language, problem.checker_source, binary_name=CHECKER_BINARY
        )
        if not compiled.ok:
            logger.error("checker compilation failed: %s", compiled.log[:500])
        return compiled.ok

    async def _run_test(self, session, run_argv, limits, test) -> TestResult:
        await session.put_file(_INPUT, test.input_data)
        await session.put_file(_ANSWER, test.answer_data)

        run = await session.run(run_argv, limits, stdin=_INPUT, stdout=_OUTPUT)
        failed = from_run_status(run.status)
        if failed is not None:
            return TestResult(
                test_index=test.index,
                verdict=failed,
                time_ms=run.cpu_time_ms,
                memory_kb=run.memory_kb,
                comment=run.message,
            )

        outcome = await run_checker(
            session, input_name=_INPUT, output_name=_OUTPUT, answer_name=_ANSWER
        )
        return TestResult(
            test_index=test.index,
            verdict=outcome.verdict,
            time_ms=run.cpu_time_ms,
            memory_kb=run.memory_kb,
            comment=outcome.comment,
            points_ratio=outcome.points_ratio,
        )

    def _aggregate(self, problem: ProblemSpec, results: list[TestResult]) -> JudgeResult:
        failure = next((r for r in results if r.verdict is not Verdict.OK), None)
        verdict = failure.verdict if failure else Verdict.OK
        return JudgeResult(
            verdict=verdict,
            score=score_tests(problem.tests, results),
            tests=results,
        )
