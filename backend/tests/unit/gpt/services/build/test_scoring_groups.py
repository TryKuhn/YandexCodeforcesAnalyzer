"""Unit tests for test-group / points configuration (build.scoring_groups)."""
import pytest

from api.user.gpt.services.build import scoring_groups as sg

_TABLE = r"""
\begin{tabular}{ | c | c | c | c | c | }
\hline
Подзадача & Баллы & Ограничения & Зависимости & Проверка \\ \hline
$0$ & -- & тесты из условия & -- & полная \\ \hline
$1$ & $30$ & $n \le 20$ & 0 & первая ошибка \\ \hline
$2$ & $70$ & $n \le 1000$ & 1 & полная \\ \hline
\end{tabular}
"""


def test_parse_scoring_groups_extracts_rows_skipping_zero():
    groups = sg.parse_scoring_groups(_TABLE)
    assert [g["group"] for g in groups] == ["1", "2"]
    assert groups[0]["points"] == 30
    assert groups[0]["feedback_policy"] == "icpc"
    assert groups[1]["feedback_policy"] == "complete"


def test_parse_scoring_groups_no_table():
    assert sg.parse_scoring_groups("no latex here") == []
    assert sg.parse_scoring_groups(None) == []


def test_subtasks_to_groups_maps_fields():
    subs = [{"group": "1", "points": 40, "depends_on": ["0"], "num_tests": 6}]
    assert sg.subtasks_to_groups(subs) == [{
        "group": "1", "points": 40, "dependencies": ["0"],
        "feedback_policy": "icpc", "num_tests": 6,
    }]


def test_subtasks_to_groups_empty():
    assert sg.subtasks_to_groups(None) == []


def test_slice_counts_uses_planned_with_remainder():
    groups = [{"points": 50, "num_tests": 3}, {"points": 50, "num_tests": 4}]
    assert sg._slice_counts(groups, 10) == [3, 7]


def test_slice_counts_proportional_fallback():
    groups = [{"points": 25, "num_tests": 0}, {"points": 75, "num_tests": 0}]
    counts = sg._slice_counts(groups, 8)
    assert sum(counts) == 8 and counts[0] >= 1


@pytest.mark.asyncio
async def test_setup_groups_and_points_enables_and_configures(monkeypatch):
    calls = {"groups": 0, "points": 0, "save": []}

    async def fake_enable_groups(*a, **k): calls["groups"] += 1
    async def fake_enable_points(*a, **k): calls["points"] += 1
    async def fake_save_test_group(**k): calls["save"].append(k)

    monkeypatch.setattr(sg, "enable_groups", fake_enable_groups)
    monkeypatch.setattr(sg, "enable_points", fake_enable_points)
    monkeypatch.setattr(sg, "save_test_group", fake_save_test_group)

    subs = [{"group": "1", "points": 100, "depends_on": [], "num_tests": 5}]
    groups = await sg.setup_groups_and_points(
        "s", 1, 2, {"enable_groups": True, "enable_points": True}, None, None,
        subtasks=subs,
    )
    assert calls["groups"] == 1 and calls["points"] == 1
    assert calls["save"][0]["points_policy"] == "complete-group"
    assert groups[0]["points"] == 100


@pytest.mark.asyncio
async def test_setup_groups_disabled_returns_empty():
    assert await sg.setup_groups_and_points(
        "s", 1, 2, {"enable_groups": False, "enable_points": False}, None, None
    ) == []


@pytest.mark.asyncio
async def test_assign_tests_to_groups_sets_ranges_and_points(monkeypatch):
    points_calls, set_calls = [], []

    async def fake_get_tests(problem_id, testset, user_id, db, no_inputs=None):
        return [
            {"index": 1, "useInStatements": True},
            {"index": 2, "useInStatements": False},
            {"index": 3, "useInStatements": False},
            {"index": 4, "useInStatements": False},
            {"index": 5, "useInStatements": False},
        ]

    async def fake_set_test_group(problem_id, testset, group, indices, user_id, db):
        set_calls.append((group, indices))

    async def fake_save_test(**k):
        points_calls.append(k)

    monkeypatch.setattr(sg, "get_tests", fake_get_tests)
    monkeypatch.setattr(sg, "set_test_group", fake_set_test_group)
    monkeypatch.setattr(sg, "save_test", fake_save_test)

    groups = [
        {"group": "1", "points": 40, "num_tests": 2},
        {"group": "2", "points": 60, "num_tests": 2},
    ]
    mapping = await sg.assign_tests_to_groups("s", 1, 2, groups, None)

    assert mapping == {"1": [2, 3], "2": [4, 5]}
    assert points_calls[0]["test_index"] == 2
    assert points_calls[0]["test_points"] == 40.0
    assert points_calls[0]["test_input"] is None


@pytest.mark.asyncio
async def test_assign_tests_to_groups_no_groups_returns_empty():
    assert await sg.assign_tests_to_groups("s", 1, 2, [], None) == {}
