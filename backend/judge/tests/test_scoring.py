"""Group and point aggregation."""
from app.engine import TestCase, Verdict, score_tests
from app.engine.result import TestResult


def _ok(index: int, ratio: float | None = None) -> TestResult:
    return TestResult(test_index=index, verdict=Verdict.OK, points_ratio=ratio)


def _fail(index: int) -> TestResult:
    return TestResult(test_index=index, verdict=Verdict.WRONG_ANSWER)


def test_ungrouped_tests_pay_per_test():
    tests = [TestCase(1, b"", b"", points=10), TestCase(2, b"", b"", points=15)]
    assert score_tests(tests, [_ok(1), _ok(2)]) == 25


def test_failed_test_pays_nothing():
    tests = [TestCase(1, b"", b"", points=10), TestCase(2, b"", b"", points=15)]
    assert score_tests(tests, [_ok(1), _fail(2)]) == 10


def test_group_pays_only_when_every_test_passes():
    tests = [
        TestCase(1, b"", b"", group="g1", points=20),
        TestCase(2, b"", b"", group="g1", points=20),
    ]
    assert score_tests(tests, [_ok(1), _ok(2)]) == 40
    assert score_tests(tests, [_ok(1), _fail(2)]) == 0


def test_unjudged_test_blocks_its_group():
    # stopping early must not pay out for a group we never finished
    tests = [
        TestCase(1, b"", b"", group="g1", points=10),
        TestCase(2, b"", b"", group="g1", points=10),
    ]
    assert score_tests(tests, [_ok(1)]) == 0


def test_groups_are_scored_independently():
    tests = [
        TestCase(1, b"", b"", group="g1", points=10),
        TestCase(2, b"", b"", group="g2", points=30),
    ]
    assert score_tests(tests, [_ok(1), _fail(2)]) == 10


def test_partial_credit_uses_the_worst_test_in_the_group():
    tests = [
        TestCase(1, b"", b"", group="g1", points=50),
        TestCase(2, b"", b"", group="g1", points=50),
    ]
    assert score_tests(tests, [_ok(1, 0.5), _ok(2, 1.0)]) == 50


def test_no_points_configured_scores_zero():
    tests = [TestCase(1, b"", b""), TestCase(2, b"", b"")]
    assert score_tests(tests, [_ok(1), _ok(2)]) == 0
