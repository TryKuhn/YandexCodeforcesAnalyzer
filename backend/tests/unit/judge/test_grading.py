"""Turning a queued submission into a verdict."""
import hashlib

import pytest
from sqlalchemy import select

from api.judge import grading
from api.judge.client import JudgeUnavailable
from models.judge.contest import JudgeContest
from models.judge.problem import JudgeProblem
from models.judge.run import JudgeRun
from models.judge.submission import JudgeSubmission
from models.judge.test import JudgeTest


class FakeStore:
    """Blob store backed by a dict."""

    def __init__(self) -> None:
        self.data: dict[str, bytes] = {}

    def seed(self, payload: bytes) -> str:
        sha = hashlib.sha256(payload).hexdigest()
        self.data[sha] = payload
        return sha

    async def get(self, sha: str) -> bytes:
        return self.data[sha]

    async def put(self, db, payload: bytes) -> str:
        return self.seed(payload)


VERDICT_OK = {
    "verdict": "OK",
    "score": 100.0,
    "max_time_ms": 12,
    "max_memory_kb": 2048,
    "first_failed_test": None,
    "compile_log": "",
    "tests": [
        {"index": 1, "verdict": "OK", "time_ms": 12, "memory_kb": 2048, "comment": "ok 5"},
        {"index": 2, "verdict": "OK", "time_ms": 8, "memory_kb": 2000, "comment": ""},
    ],
}


@pytest.fixture
def store() -> FakeStore:
    return FakeStore()


async def _make_submission(db, store: FakeStore, *, with_answers=True, tests=2):
    contest = JudgeContest(name="c")
    db.add(contest)
    problem = JudgeProblem(title="A+B", checker_sha=store.seed(b"// checker"))
    db.add(problem)
    await db.flush()

    for i in range(1, tests + 1):
        db.add(
            JudgeTest(
                problem_id=problem.id,
                index=i,
                input_sha=store.seed(f"{i} {i}\n".encode()),
                answer_sha=store.seed(f"{2 * i}\n".encode()) if with_answers else None,
            )
        )
    submission = JudgeSubmission(
        problem_id=problem.id,
        contest_id=contest.id,
        user_id=7,
        language="cpp",
        source_sha=store.seed(b"int main(){}"),
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)
    return submission


async def test_verdict_and_runs_are_stored(db, store, monkeypatch):
    submission = await _make_submission(db, store)

    async def fake_judge(**kwargs):
        return VERDICT_OK

    monkeypatch.setattr(grading, "judge_submission", fake_judge)
    await grading.grade(db, store, submission.id)

    await db.refresh(submission)
    assert submission.status == "judged"
    assert submission.verdict == "OK"
    assert submission.score == 100.0
    assert submission.judged_at is not None

    runs = (await db.execute(select(JudgeRun))).scalars().all()
    assert [r.test_index for r in runs] == [1, 2]
    assert runs[0].checker_comment == "ok 5"


async def test_everything_the_judge_needs_is_sent(db, store, monkeypatch):
    submission = await _make_submission(db, store)
    captured = {}

    async def fake_judge(**kwargs):
        captured.update(kwargs)
        return VERDICT_OK

    monkeypatch.setattr(grading, "judge_submission", fake_judge)
    await grading.grade(db, store, submission.id)

    assert captured["source"] == b"int main(){}"
    assert captured["language"] == "cpp"
    assert captured["checker"] == b"// checker"
    assert [t.input_data for t in captured["tests"]] == [b"1 1\n", b"2 2\n"]
    assert [t.answer_data for t in captured["tests"]] == [b"2\n", b"4\n"]


async def test_failing_verdict_records_the_first_bad_test(db, store, monkeypatch):
    submission = await _make_submission(db, store)

    async def fake_judge(**kwargs):
        return {
            **VERDICT_OK,
            "verdict": "WA",
            "score": 0.0,
            "first_failed_test": 2,
            "tests": [
                {"index": 1, "verdict": "OK", "time_ms": 5, "memory_kb": 100, "comment": ""},
                {"index": 2, "verdict": "WA", "time_ms": 6, "memory_kb": 100,
                 "comment": "expected 4, found 5"},
            ],
        }

    monkeypatch.setattr(grading, "judge_submission", fake_judge)
    await grading.grade(db, store, submission.id)

    await db.refresh(submission)
    assert submission.verdict == "WA"
    assert submission.first_failed_test == 2


async def test_compile_log_is_stored_as_a_blob(db, store, monkeypatch):
    submission = await _make_submission(db, store)

    async def fake_judge(**kwargs):
        return {**VERDICT_OK, "verdict": "CE", "compile_log": "main.cpp:1: error", "tests": []}

    monkeypatch.setattr(grading, "judge_submission", fake_judge)
    await grading.grade(db, store, submission.id)

    await db.refresh(submission)
    assert submission.compile_log_sha is not None
    assert await store.get(submission.compile_log_sha) == b"main.cpp:1: error"


async def test_tests_without_jury_answers_are_refused(db, store, monkeypatch):
    submission = await _make_submission(db, store, with_answers=False)

    with pytest.raises(ValueError, match="jury answers"):
        await grading.grade(db, store, submission.id)


async def test_problem_without_tests_is_refused(db, store):
    submission = await _make_submission(db, store, tests=0)
    with pytest.raises(ValueError, match="no tests"):
        await grading.grade(db, store, submission.id)


async def test_unreachable_judge_propagates_for_retry(db, store, monkeypatch):
    submission = await _make_submission(db, store)

    async def fake_judge(**kwargs):
        raise JudgeUnavailable("connection refused")

    monkeypatch.setattr(grading, "judge_submission", fake_judge)

    # the worker retries on exceptions, so the submission is not lost
    with pytest.raises(JudgeUnavailable):
        await grading.grade(db, store, submission.id)

    await db.refresh(submission)
    assert submission.status == "running"
    assert submission.verdict is None
