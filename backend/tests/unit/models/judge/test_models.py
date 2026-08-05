"""Judge domain models: blob-hash references, dedup, cascades."""
import hashlib

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from models.judge import (JudgeProblem, JudgeRun, JudgeSubmission, JudgeTest,
                          JudgeVerdict)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def test_verdict_codes_match_the_oracle_contract():
    # YCA-407 maps solution tags to exactly these codes
    assert {v.value for v in JudgeVerdict} == {
        "OK", "WA", "TLE", "MLE", "RE", "PE", "CE", "XX",
    }


async def test_problem_with_tests_roundtrip(db):
    problem = JudgeProblem(
        title="A+B",
        checker_sha=_sha(b"checker"),
        tests=[
            JudgeTest(index=2, input_sha=_sha(b"in2")),
            JudgeTest(index=1, input_sha=_sha(b"in1"), answer_sha=_sha(b"ans1")),
        ],
    )
    db.add(problem)
    await db.commit()
    await db.refresh(problem)

    assert problem.time_limit_ms == 1000
    assert problem.memory_limit_mb == 256
    # relationship keeps tests in test order, not insertion order
    assert [t.index for t in problem.tests] == [1, 2]
    assert problem.tests[0].answer_sha == _sha(b"ans1")


async def test_test_index_is_unique_within_problem(db):
    problem = JudgeProblem(title="p")
    db.add(problem)
    await db.flush()
    db.add(JudgeTest(problem_id=problem.id, index=1, input_sha=_sha(b"a")))
    db.add(JudgeTest(problem_id=problem.id, index=1, input_sha=_sha(b"b")))

    with pytest.raises(IntegrityError):
        await db.commit()


async def test_same_input_hash_is_shared_between_problems(db):
    # dedup across problems: two rows, one blob
    shared = _sha(b"common test input")
    first = JudgeProblem(title="p1", tests=[JudgeTest(index=1, input_sha=shared)])
    second = JudgeProblem(title="p2", tests=[JudgeTest(index=1, input_sha=shared)])
    db.add_all([first, second])
    await db.commit()

    rows = (await db.execute(
        select(JudgeTest).where(JudgeTest.input_sha == shared)
    )).scalars().all()
    assert len(rows) == 2
    assert rows[0].problem_id != rows[1].problem_id


async def test_deleting_problem_removes_its_tests(db):
    problem = JudgeProblem(title="gone", tests=[JudgeTest(index=1, input_sha=_sha(b"x"))])
    db.add(problem)
    await db.commit()

    await db.delete(problem)
    await db.commit()

    assert (await db.execute(select(JudgeTest))).scalars().all() == []


async def test_submission_defaults(db):
    problem = JudgeProblem(title="p")
    db.add(problem)
    await db.flush()
    submission = JudgeSubmission(
        problem_id=problem.id, language="cpp", source_sha=_sha(b"src")
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    assert submission.status == "queued"
    assert submission.verdict is None
    assert submission.judged_at is None


async def test_judged_submission_with_runs(db):
    problem = JudgeProblem(title="p")
    db.add(problem)
    await db.flush()
    submission = JudgeSubmission(
        problem_id=problem.id,
        language="python",
        source_sha=_sha(b"src"),
        status="judged",
        verdict=JudgeVerdict.WRONG_ANSWER.value,
        first_failed_test=2,
        runs=[
            JudgeRun(test_index=1, verdict="OK", time_ms=12, memory_kb=800),
            JudgeRun(test_index=2, verdict="WA", checker_comment="expected 3, got 4"),
        ],
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    assert submission.verdict == "WA"
    assert [r.verdict for r in submission.runs] == ["OK", "WA"]
    assert submission.runs[1].checker_comment == "expected 3, got 4"


async def test_run_per_test_is_unique(db):
    problem = JudgeProblem(title="p")
    db.add(problem)
    await db.flush()
    submission = JudgeSubmission(problem_id=problem.id, language="cpp", source_sha=_sha(b"s"))
    db.add(submission)
    await db.flush()
    db.add(JudgeRun(submission_id=submission.id, test_index=1, verdict="OK"))
    db.add(JudgeRun(submission_id=submission.id, test_index=1, verdict="WA"))

    with pytest.raises(IntegrityError):
        await db.commit()


async def test_deleting_submission_removes_runs(db):
    problem = JudgeProblem(title="p")
    db.add(problem)
    await db.flush()
    submission = JudgeSubmission(
        problem_id=problem.id,
        language="cpp",
        source_sha=_sha(b"s"),
        runs=[JudgeRun(test_index=1, verdict="OK")],
    )
    db.add(submission)
    await db.commit()

    await db.delete(submission)
    await db.commit()

    assert (await db.execute(select(JudgeRun))).scalars().all() == []
