"""testlib checker protocol: exit code decides the verdict, not a diff."""
from app.engine import Verdict, run_checker
from app.sandbox.result import RunResult, RunStatus

from .fakes import FakeSession


async def _check(result: RunResult, comment: bytes = b"") -> object:
    session = FakeSession([result])
    session.files["checker.err"] = comment
    return await run_checker(
        session, input_name="input.txt", output_name="output.txt", answer_name="answer.txt"
    )


async def test_exit_zero_is_ok():
    outcome = await _check(RunResult(status=RunStatus.OK, exit_code=0))
    assert outcome.verdict is Verdict.OK


async def test_exit_one_is_wrong_answer():
    outcome = await _check(RunResult(status=RunStatus.RUNTIME_ERROR, exit_code=1), b"wrong answer 1st number differs")
    assert outcome.verdict is Verdict.WRONG_ANSWER
    assert "1st number differs" in outcome.comment


async def test_exit_two_is_presentation_error():
    outcome = await _check(RunResult(status=RunStatus.RUNTIME_ERROR, exit_code=2))
    assert outcome.verdict is Verdict.PRESENTATION_ERROR


async def test_checker_fail_is_internal_not_contestants_fault():
    # _fail means the checker is broken; blaming the solution would be dishonest
    outcome = await _check(RunResult(status=RunStatus.RUNTIME_ERROR, exit_code=3), b"FAIL jury answer is invalid")
    assert outcome.verdict is Verdict.INTERNAL_ERROR


async def test_partial_points_are_parsed():
    outcome = await _check(RunResult(status=RunStatus.RUNTIME_ERROR, exit_code=7), b"points 0.5 half right")
    assert outcome.verdict is Verdict.OK
    assert outcome.points_ratio == 0.5


async def test_points_without_a_number_defaults_to_zero():
    outcome = await _check(RunResult(status=RunStatus.RUNTIME_ERROR, exit_code=7), b"partially correct")
    assert outcome.points_ratio == 0.0


async def test_unknown_exit_code_is_internal_error():
    outcome = await _check(RunResult(status=RunStatus.RUNTIME_ERROR, exit_code=42))
    assert outcome.verdict is Verdict.INTERNAL_ERROR


async def test_hanging_checker_is_internal_error():
    outcome = await _check(RunResult(status=RunStatus.TIME_LIMIT))
    assert outcome.verdict is Verdict.INTERNAL_ERROR
    assert "timed out" in outcome.comment
