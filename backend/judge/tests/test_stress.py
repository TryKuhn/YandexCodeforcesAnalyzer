"""Counterexample hunting."""
from app.sandbox.result import RunResult, RunStatus
from app.stress import StressTester

from .fakes import FakeSandbox, FakeSession

_OK = RunResult(status=RunStatus.OK)
# four compilations happen before the loop starts
_BUILD = [_OK, _OK, _OK, _OK]


async def _hunt(results, iterations=3, **kwargs):
    session = FakeSession(results)
    tester = StressTester(FakeSandbox([session]))
    return await tester.hunt(
        candidate=b"// candidate",
        reference=b"// reference",
        generator=b"// generator",
        checker=b"// checker",
        iterations=iterations,
        **kwargs,
    ), session


async def test_clean_candidate_survives_every_round():
    # per round: generate, reference, candidate, checker
    result, _ = await _hunt(_BUILD + [_OK] * 12, iterations=3)
    assert not result.found
    assert result.ok
    assert result.iterations == 3


async def test_wrong_answer_is_caught_with_a_counterexample():
    rounds = [_OK, _OK, _OK, RunResult(status=RunStatus.RUNTIME_ERROR, exit_code=1)]
    session_results = _BUILD + rounds
    session = FakeSession(session_results)
    session.files["input.txt"] = b"5 7\n"
    session.files["expected.txt"] = b"12\n"
    session.files["actual.txt"] = b"-2\n"
    session.files["checker.err"] = b"expected 12, found -2"

    result = await StressTester(FakeSandbox([session])).hunt(
        candidate=b"//", reference=b"//", generator=b"//", checker=b"//", iterations=5
    )

    assert result.found
    assert result.iterations == 1
    assert result.counterexample.input_data == b"5 7\n"
    assert result.counterexample.expected == b"12\n"
    assert result.counterexample.actual == b"-2\n"
    assert "expected 12" in result.counterexample.reason


async def test_crashing_candidate_is_a_counterexample_too():
    rounds = [_OK, _OK, RunResult(status=RunStatus.RUNTIME_ERROR, signal=11)]
    result, _ = await _hunt(_BUILD + rounds, iterations=5)
    assert result.found
    assert result.counterexample.reason == "RE"


async def test_slow_candidate_is_a_counterexample():
    rounds = [_OK, _OK, RunResult(status=RunStatus.TIME_LIMIT)]
    result, _ = await _hunt(_BUILD + rounds, iterations=5)
    assert result.found
    assert result.counterexample.reason == "TLE"


async def test_search_stops_at_the_first_break():
    rounds = [_OK, _OK, RunResult(status=RunStatus.MEMORY_LIMIT)]
    result, session = await _hunt(_BUILD + rounds, iterations=50)
    assert result.found
    assert result.iterations == 1
    # nothing ran after the break was found
    assert len(session.runs) == len(_BUILD) + len(rounds)


async def test_seed_reaches_the_generator():
    result, session = await _hunt(_BUILD + [_OK] * 8, iterations=2, gen_args="100 {seed}")
    generator_runs = [r for r in session.runs if "./generator" in r["argv"]]
    assert generator_runs[0]["argv"][-2:] == ["100", "1"]
    assert generator_runs[1]["argv"][-2:] == ["100", "2"]


async def test_broken_candidate_build_is_reported_not_a_counterexample():
    session = FakeSession([RunResult(status=RunStatus.RUNTIME_ERROR, exit_code=1)])
    session.files["compile_candidate.log"] = b"candidate.cpp:1: error"
    result = await StressTester(FakeSandbox([session])).hunt(
        candidate=b"//", reference=b"//", generator=b"//", checker=b"//"
    )
    assert not result.found
    assert not result.ok
    assert result.failed_stage == "compile candidate"


async def test_failing_jury_solution_stops_the_hunt():
    rounds = [_OK, RunResult(status=RunStatus.RUNTIME_ERROR, signal=11)]
    result, _ = await _hunt(_BUILD + rounds, iterations=5)
    assert not result.found
    assert result.failed_stage == "reference"


async def test_broken_generator_stops_the_hunt():
    rounds = [RunResult(status=RunStatus.TIME_LIMIT)]
    result, _ = await _hunt(_BUILD + rounds, iterations=5)
    assert not result.found
    assert result.failed_stage == "generator"


async def test_broken_checker_is_not_blamed_on_the_candidate():
    rounds = [_OK, _OK, _OK, RunResult(status=RunStatus.RUNTIME_ERROR, exit_code=3)]
    session = FakeSession(_BUILD + rounds)
    session.files["checker.err"] = b"FAIL jury answer is invalid"
    result = await StressTester(FakeSandbox([session])).hunt(
        candidate=b"//", reference=b"//", generator=b"//", checker=b"//", iterations=5
    )
    assert not result.found
    assert result.failed_stage == "checker"


async def test_progress_is_reported_per_round():
    seen = []

    async def progress(done, total):
        seen.append((done, total))

    session = FakeSession(_BUILD + [_OK] * 8)
    await StressTester(FakeSandbox([session])).hunt(
        candidate=b"//", reference=b"//", generator=b"//", checker=b"//",
        iterations=2, progress=progress,
    )
    assert seen == [(1, 2), (2, 2)]
