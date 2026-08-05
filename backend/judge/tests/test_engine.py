"""End-to-end judging over a scripted sandbox."""
from app.engine import JudgingEngine, ProblemSpec, SubmissionSpec, TestCase, Verdict
from app.sandbox.result import RunResult, RunStatus

from .fakes import FakeSandbox, FakeSession

_OK = RunResult(status=RunStatus.OK)


def _problem(tests: list[TestCase], **kwargs) -> ProblemSpec:
    return ProblemSpec(tests=tests, checker_source=b"// checker", **kwargs)


def _submission() -> SubmissionSpec:
    return SubmissionSpec(source=b"int main(){}", language_id="cpp")


def _tests(n: int, **kwargs) -> list[TestCase]:
    return [TestCase(i, b"in", b"ans", **kwargs) for i in range(1, n + 1)]


async def _judge(results: list[RunResult], tests: list[TestCase], **kwargs):
    session = FakeSession(results)
    engine = JudgingEngine(FakeSandbox([session]))
    return await engine.judge(_problem(tests, **kwargs), _submission())


async def test_all_tests_pass():
    # compile, checker build, then (run + check) per test
    outcome = await _judge([_OK, _OK, _OK, _OK, _OK, _OK], _tests(2))
    assert outcome.verdict is Verdict.OK
    assert [t.verdict for t in outcome.tests] == [Verdict.OK, Verdict.OK]


async def test_compile_error_short_circuits():
    session = FakeSession([RunResult(status=RunStatus.RUNTIME_ERROR, exit_code=1)])
    session.files["compile.log"] = b"main.cpp:1: error: bad"
    engine = JudgingEngine(FakeSandbox([session]))

    outcome = await engine.judge(_problem(_tests(3)), _submission())

    assert outcome.verdict is Verdict.COMPILE_ERROR
    assert "error: bad" in outcome.compile_log
    assert outcome.tests == []


async def test_timeout_on_a_test_is_reported_as_tle():
    outcome = await _judge([_OK, _OK, RunResult(status=RunStatus.TIME_LIMIT)], _tests(2))
    assert outcome.verdict is Verdict.TIME_LIMIT
    assert outcome.first_failed_test == 1


async def test_memory_limit_is_not_reported_as_runtime_error():
    outcome = await _judge([_OK, _OK, RunResult(status=RunStatus.MEMORY_LIMIT)], _tests(1))
    assert outcome.verdict is Verdict.MEMORY_LIMIT


async def test_runtime_error_is_reported():
    outcome = await _judge(
        [_OK, _OK, RunResult(status=RunStatus.RUNTIME_ERROR, signal=11)], _tests(1)
    )
    assert outcome.verdict is Verdict.RUNTIME_ERROR


async def test_checker_verdict_wins_over_a_clean_run():
    # process exited fine, but the answer is wrong: only the checker knows
    outcome = await _judge(
        [_OK, _OK, _OK, RunResult(status=RunStatus.RUNTIME_ERROR, exit_code=1)], _tests(1)
    )
    assert outcome.verdict is Verdict.WRONG_ANSWER


async def test_stops_at_first_failure_by_default():
    outcome = await _judge(
        [_OK, _OK, RunResult(status=RunStatus.TIME_LIMIT)], _tests(5)
    )
    # judging stopped instead of burning time on the remaining tests
    assert len(outcome.tests) == 1


async def test_ioi_mode_judges_every_test():
    results = [_OK, _OK] + [_OK, RunResult(status=RunStatus.RUNTIME_ERROR, exit_code=1)] * 3
    outcome = await _judge(results, _tests(3), stop_on_first_failure=False)
    assert len(outcome.tests) == 3


async def test_score_is_aggregated_over_groups():
    tests = [
        TestCase(1, b"in", b"ans", group="g1", points=30),
        TestCase(2, b"in", b"ans", group="g2", points=70),
    ]
    # test 1 passes, test 2 fails the checker
    results = [_OK, _OK, _OK, _OK, _OK, RunResult(status=RunStatus.RUNTIME_ERROR, exit_code=1)]
    session = FakeSession(results)
    engine = JudgingEngine(FakeSandbox([session]))

    outcome = await engine.judge(
        _problem(tests, stop_on_first_failure=False), _submission()
    )

    assert outcome.score == 30
    assert outcome.verdict is Verdict.WRONG_ANSWER


async def test_progress_is_reported_per_test():
    seen = []

    async def progress(done, total):
        seen.append((done, total))

    session = FakeSession([_OK] * 8)
    engine = JudgingEngine(FakeSandbox([session]))
    await engine.judge(_problem(_tests(3)), _submission(), progress=progress)

    assert seen == [(1, 3), (2, 3), (3, 3)]


async def test_broken_checker_build_is_internal_error():
    session = FakeSession([_OK, RunResult(status=RunStatus.RUNTIME_ERROR, exit_code=1)])
    session.files["compile_checker.log"] = b"checker.cpp: error"
    engine = JudgingEngine(FakeSandbox([session]))

    outcome = await engine.judge(_problem(_tests(1)), _submission())

    assert outcome.verdict is Verdict.INTERNAL_ERROR


async def test_timing_stats_are_collected():
    run = RunResult(status=RunStatus.OK, cpu_time_ms=120, memory_kb=4096)
    outcome = await _judge([_OK, _OK, run, _OK], _tests(1))
    assert outcome.max_time_ms == 120
    assert outcome.max_memory_kb == 4096
