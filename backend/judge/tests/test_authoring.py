"""Local problem building: generate, validate, solve."""
import pytest

from app.authoring import (GeneratedTest, LocalBuildLock, LockBusy, ManualTest,
                           ProblemBuilder, ProblemSource)
from app.sandbox.result import RunResult, RunStatus

from .fakes import FakeSandbox, FakeSession

_OK = RunResult(status=RunStatus.OK)


def _source(**overrides) -> ProblemSource:
    base = {
        "name": "aplusb",
        "main_solution": b"// jury solution",
        "checker": b"// checker",
    }
    base.update(overrides)
    return ProblemSource(**base)


async def _build(session: FakeSession, source: ProblemSource):
    return await ProblemBuilder(FakeSandbox([session])).build(source)


async def test_manual_test_gets_its_answer_from_the_jury_solution():
    session = FakeSession([_OK, _OK])
    session.files["answer.txt"] = b"5\n"
    result = await _build(session, _source(manual_tests=[ManualTest(b"2 3\n", points=100)]))

    assert result.ok
    assert len(result.tests) == 1
    assert result.tests[0].input_data == b"2 3\n"
    assert result.tests[0].answer_data == b"5\n"
    assert result.tests[0].origin == "manual"


async def test_generated_test_comes_from_the_generator():
    session = FakeSession([_OK, _OK, _OK, _OK])
    session.files["input.txt"] = b"7 8\n"
    session.files["answer.txt"] = b"15\n"
    result = await _build(
        session,
        _source(generator=b"// gen", generated_tests=[GeneratedTest(args="10 20 seed")]),
    )

    assert result.ok
    assert result.tests[0].input_data == b"7 8\n"
    assert "generated" in result.tests[0].origin


async def test_generator_arguments_reach_the_binary():
    session = FakeSession([_OK, _OK, _OK, _OK])
    await _build(
        session,
        _source(generator=b"// gen", generated_tests=[GeneratedTest(args="10 20 seed")]),
    )
    # first two runs compile, the third runs the generator
    generator_run = session.runs[2]["argv"]
    assert generator_run[-3:] == ["10", "20", "seed"]


async def test_invalid_test_blocks_the_build():
    # validator rejects: compile main, compile validator, validate -> fail
    session = FakeSession([_OK, _OK, RunResult(status=RunStatus.RUNTIME_ERROR, exit_code=1)])
    session.files["stage.err"] = b"FAIL n must be positive"
    result = await _build(
        session,
        _source(validator=b"// val", manual_tests=[ManualTest(b"-1 -1\n")]),
    )

    assert not result.ok
    assert result.failed_stage == "validator"
    assert "n must be positive" in result.log


async def test_broken_generator_stops_the_build():
    session = FakeSession([_OK, _OK, RunResult(status=RunStatus.RUNTIME_ERROR, exit_code=1)])
    result = await _build(
        session,
        _source(generator=b"// gen", generated_tests=[GeneratedTest(args="bad")]),
    )

    assert not result.ok
    assert result.failed_stage == "generator"


async def test_main_solution_failing_is_reported_as_jury_error():
    session = FakeSession([_OK, RunResult(status=RunStatus.TIME_LIMIT)])
    result = await _build(session, _source(manual_tests=[ManualTest(b"2 3\n")]))

    assert not result.ok
    assert result.failed_stage == "main solution"
    assert "TL" in result.error


async def test_uncompilable_jury_code_is_reported():
    session = FakeSession([RunResult(status=RunStatus.RUNTIME_ERROR, exit_code=1)])
    session.files["compile.log"] = b"main.cpp:1: error"
    result = await _build(session, _source(manual_tests=[ManualTest(b"2 3\n")]))

    assert not result.ok
    assert result.failed_stage == "compile main solution"


async def test_problem_without_tests_is_rejected():
    result = await _build(FakeSession([_OK]), _source())
    assert not result.ok
    assert result.failed_stage == "tests"


async def test_points_and_groups_survive_the_build():
    session = FakeSession([_OK, _OK])
    session.files["answer.txt"] = b"5\n"
    result = await _build(
        session, _source(manual_tests=[ManualTest(b"2 3\n", group="g1", points=40)])
    )

    assert result.tests[0].group == "g1"
    assert result.total_points == 40


async def test_package_carries_limits_and_checker():
    session = FakeSession([_OK, _OK])
    result = await _build(
        session,
        _source(manual_tests=[ManualTest(b"2 3\n")], time_limit_ms=2500, memory_limit_mb=512),
    )

    assert result.checker == b"// checker"
    assert result.time_limit_ms == 2500
    assert result.memory_limit_mb == 512


async def test_lock_keeps_two_builds_apart():
    lock = LocalBuildLock()
    async with lock.hold("aplusb"):
        with pytest.raises(LockBusy):
            async with lock.hold("aplusb"):
                pass


async def test_lock_is_released_after_a_failure():
    lock = LocalBuildLock()
    with pytest.raises(RuntimeError):
        async with lock.hold("aplusb"):
            raise RuntimeError("build blew up")
    # the next build must not be blocked by the previous crash
    async with lock.hold("aplusb"):
        pass


async def test_different_problems_build_in_parallel():
    lock = LocalBuildLock()
    async with lock.hold("a"), lock.hold("b"):
        pass
