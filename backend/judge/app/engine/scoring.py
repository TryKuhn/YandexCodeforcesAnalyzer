"""Turning per-test results into a score."""
from .result import TestResult
from .spec import TestCase
from .verdict import Verdict


def score_tests(tests: list[TestCase], results: list[TestResult]) -> float:
    """Sum earned points: a group pays only if every one of its tests passed."""
    by_index = {r.test_index: r for r in results}
    total = 0.0
    grouped: dict[str, list[TestCase]] = {}

    for test in tests:
        if test.group is None:
            result = by_index.get(test.index)
            if result and result.verdict is Verdict.OK:
                total += test.points * (
                    result.points_ratio if result.points_ratio is not None else 1.0
                )
        else:
            grouped.setdefault(test.group, []).append(test)

    for members in grouped.values():
        outcomes = [by_index.get(t.index) for t in members]
        # an unjudged test counts as a failure: partial data must not pay out
        if not all(o and o.verdict is Verdict.OK for o in outcomes):
            continue
        ratios = [o.points_ratio if o and o.points_ratio is not None else 1.0 for o in outcomes]
        group_points = sum(t.points for t in members)
        total += group_points * min(ratios)

    return round(total, 6)
