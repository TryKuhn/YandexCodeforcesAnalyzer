"""Checker, validators, interactor and their tests."""
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.polygon.client import call, choice
from api.user.polygon.constants import (CHECKER_TEST_VERDICTS,
                                        VALIDATOR_TEST_VERDICTS)
from api.user.polygon.methods.files import save_file


async def get_checker(problem_id: int, user_id: int, db: AsyncSession) -> str:
    """``problem.checker`` -> name of the current checker."""
    return await call("problem.checker", user_id, db, problemId=problem_id) or ""


async def set_checker(problem_id: int, checker: str, user_id: int, db: AsyncSession) -> None:
    """``problem.setChecker`` -- use an uploaded source (or ``std::...``) as the checker."""
    await call("problem.setChecker", user_id, db, problemId=problem_id, checker=checker)


async def get_validator(problem_id: int, user_id: int, db: AsyncSession) -> str:
    """``problem.validator`` -> name of the current validator."""
    return await call("problem.validator", user_id, db, problemId=problem_id) or ""


async def set_validator(
    problem_id: int, validator: str, user_id: int, db: AsyncSession
) -> None:
    """``problem.setValidator``."""
    await call("problem.setValidator", user_id, db, problemId=problem_id, validator=validator)


async def get_extra_validators(
    problem_id: int, user_id: int, db: AsyncSession
) -> list[str]:
    """``problem.extraValidators`` -> names of the extra validators."""
    result = await call("problem.extraValidators", user_id, db, problemId=problem_id)
    return result if isinstance(result, list) else []


async def get_interactor(problem_id: int, user_id: int, db: AsyncSession) -> str:
    """``problem.interactor`` -> name of the current interactor."""
    return await call("problem.interactor", user_id, db, problemId=problem_id) or ""


async def set_interactor(
    problem_id: int, interactor: str, user_id: int, db: AsyncSession
) -> None:
    """``problem.setInteractor``."""
    await call(
        "problem.setInteractor", user_id, db, problemId=problem_id, interactor=interactor
    )


# --- Upload a source + assign it (composite operations) ----------------------
async def upload_checker(
    problem_id: int, name: str, source: str, user_id: int, db: AsyncSession
) -> None:
    """Upload the checker source (saveFile type=source) and set it."""
    await save_file(problem_id, "source", name, source, user_id, db)
    await set_checker(problem_id, name, user_id, db)


async def upload_validator(
    problem_id: int, name: str, source: str, user_id: int, db: AsyncSession
) -> None:
    """Upload the validator source and set it."""
    await save_file(problem_id, "source", name, source, user_id, db)
    await set_validator(problem_id, name, user_id, db)


async def upload_interactor(
    problem_id: int, name: str, source: str, user_id: int, db: AsyncSession
) -> None:
    """Upload the interactor source and set it."""
    await save_file(problem_id, "source", name, source, user_id, db)
    await set_interactor(problem_id, name, user_id, db)


# --- Validator and checker tests ----------------------------------------------
async def get_validator_tests(
    problem_id: int, user_id: int, db: AsyncSession
) -> list[dict[str, Any]]:
    """``problem.validatorTests`` → ``ValidatorTest[]``."""
    result = await call("problem.validatorTests", user_id, db, problemId=problem_id)
    return result if isinstance(result, list) else []


async def save_validator_test(
    problem_id: int,
    test_index: int,
    user_id: int,
    db: AsyncSession,
    *,
    test_input: str | None = None,
    test_verdict: str | None = None,
    check_existing: bool | None = None,
    test_group: str | None = None,
    testset: str | None = None,
) -> None:
    """``problem.saveValidatorTest`` (adding a test needs input and verdict)."""
    method = "problem.saveValidatorTest"
    await call(
        method, user_id, db,
        problemId=problem_id,
        testIndex=test_index,
        testInput=test_input,
        testVerdict=choice(test_verdict, VALIDATOR_TEST_VERDICTS, "testVerdict", method=method),
        checkExisting=check_existing,
        testGroup=test_group,
        testset=testset,
    )


async def get_checker_tests(
    problem_id: int, user_id: int, db: AsyncSession
) -> list[dict[str, Any]]:
    """``problem.checkerTests`` → ``CheckerTest[]``."""
    result = await call("problem.checkerTests", user_id, db, problemId=problem_id)
    return result if isinstance(result, list) else []


async def save_checker_test(
    problem_id: int,
    test_index: int,
    user_id: int,
    db: AsyncSession,
    *,
    test_input: str | None = None,
    test_output: str | None = None,
    test_answer: str | None = None,
    test_verdict: str | None = None,
    check_existing: bool | None = None,
) -> None:
    """``problem.saveCheckerTest`` (adding a test needs input/output/answer/verdict)."""
    method = "problem.saveCheckerTest"
    await call(
        method, user_id, db,
        problemId=problem_id,
        testIndex=test_index,
        testInput=test_input,
        testOutput=test_output,
        testAnswer=test_answer,
        testVerdict=choice(test_verdict, CHECKER_TEST_VERDICTS, "testVerdict", method=method),
        checkExisting=check_existing,
    )
