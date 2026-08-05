"""Judging engine: runs a submission against tests and produces a verdict."""
from .checker import CheckOutcome, run_checker
from .judge import JudgingEngine
from .result import JudgeResult, TestResult
from .scoring import score_tests
from .spec import ProblemSpec, SubmissionSpec, TestCase
from .verdict import Verdict, from_run_status

__all__ = [
    "CheckOutcome",
    "JudgeResult",
    "JudgingEngine",
    "ProblemSpec",
    "SubmissionSpec",
    "TestCase",
    "TestResult",
    "Verdict",
    "from_run_status",
    "run_checker",
    "score_tests",
]
