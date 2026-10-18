import pytest

from authoring.pipeline.groups import (
    PlanError,
    assign,
    build_script,
    expand_lines,
    normalize_plan,
    plan_from_snapshot,
    scoring_section,
)
from tests.fakes import expand_freemarker

PLAN = {
    "use_groups": True,
    "groups": [
        {"name": "0", "samples": True, "points": 0, "description": "тесты из условия"},
        {"name": "1", "points": 30, "description": "$n \\le 10$", "dependencies": ["0"],
         "generator": "gen_small", "cases": [{"args": "10 random", "count": 3}, {"args": "10 max", "count": 1}]},
        {"name": "2", "points": 70, "description": "без ограничений & 100%", "dependencies": ["0", "1"],
         "generator": "gen_big", "cases": [{"args": "200000 random", "count": 2}]},
    ],
}


def test_normalize_valid_plan():
    plan = normalize_plan(PLAN)
    assert plan.use_groups
    assert [g.name for g in plan.groups] == ["0", "1", "2"]
    assert plan.total_points == 100
    assert plan.samples_group and plan.samples_group.name == "0"
    assert [g.test_count for g in plan.generated_groups] == [4, 2]
    assert plan.groups[2].dependencies == ["0", "1"]


@pytest.mark.parametrize("mutate, message", [
    (lambda p: p["groups"].append({"name": "1", "cases": [{"args": "", "count": 1}]}), "дважды"),
    (lambda p: p["groups"][1].update(dependencies=["2"]), "выше по списку"),
    (lambda p: p["groups"][0].update(points=5), "0 баллов"),
    (lambda p: p["groups"][1].update(cases=[]), "нет ни одного теста"),
    (lambda p: p["groups"][1].update(generator="gen-small"), "имя генератора"),
    (lambda p: p["groups"][1]["cases"][0].update(args="1; rm -rf /"), "недопустимые символы"),
    (lambda p: p["groups"][1]["cases"][0].update(count=0), "count"),
    (lambda p: p["groups"][1].update(points=-1), "отрицательными"),
    (lambda p: p["groups"][1].update(name="группа"), "латиница"),
    (lambda p: p.update(groups=[]), "нет групп"),
])
def test_normalize_rejects(mutate, message):
    import copy
    raw = copy.deepcopy(PLAN)
    mutate(raw)
    with pytest.raises(PlanError, match=message):
        normalize_plan(raw)


def test_plan_without_groups():
    plan = normalize_plan({"use_groups": False, "groups": [
        {"name": "main", "generator": "gen", "points": 50, "cases": [{"args": "5", "count": 2}]}]})
    assert not plan.use_groups and plan.groups[0].points == 0
    assert scoring_section(plan) == ""
    with pytest.raises(PlanError, match="одного набора"):
        normalize_plan({"use_groups": False, "groups": [
            {"name": "a", "cases": [{"args": "", "count": 1}]}, {"name": "b", "cases": [{"args": "", "count": 1}]}]})


def test_script_lines_are_unique_and_match_expansion():
    plan = normalize_plan(PLAN)
    script = build_script(plan)
    assert "<#list 1..3 as i>" in script
    assert "gen_small 10 random ${i + 0} > $" in script
    assert "gen_small 10 max 4 > $" in script
    assert "gen_big 200000 random ${i + 4} > $" in script
    expanded = expand_freemarker(script)
    lines = expand_lines(plan)
    assert [f"{line.command} > $" for line in lines] == expanded
    assert len(set(expanded)) == len(expanded) == 6
    assert [line.group for line in lines] == ["1", "1", "1", "1", "2", "2"]


def test_assign_puts_group_points_on_one_test():
    plan = normalize_plan(PLAN)
    lines = expand_lines(plan)
    tests = [
        {"index": 1, "manual": True, "useInStatements": True},
        {"index": 2, "manual": True, "useInStatements": True},
        *[{"index": 3 + i, "manual": False} for i in range(len(lines))],
    ]
    a = assign(plan, tests, lines)
    assert a.groups == {"0": [1, 2], "1": [3, 4, 5, 6], "2": [7, 8]}
    assert a.points == {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 30, 7: 0, 8: 70}
    assert a.policies["1"] == ("COMPLETE_GROUP", "ICPC", ["0"])
    assert a.policies["0"] == ("COMPLETE_GROUP", "COMPLETE", [])
    assert a.warnings == []


def test_assign_reports_extra_manual_tests_and_count_mismatch():
    plan = normalize_plan(PLAN)
    lines = expand_lines(plan)
    tests = [{"index": 1, "manual": True, "useInStatements": False},
             *[{"index": 2 + i, "manual": False} for i in range(len(lines))]]
    a = assign(plan, tests, lines)
    assert 1 in a.groups["2"] and "ручной тест 1" in a.warnings[0]
    assert "в группе примеров 0 нет тестов" in a.warnings[1]
    with pytest.raises(PlanError, match="сгенерированных тестов"):
        assign(plan, tests[:-1], lines)


def test_scoring_section_escapes_text_but_not_math():
    section = scoring_section(normalize_plan(PLAN))
    assert "\\begin{tabular}{|c|c|p{7cm}|c|}" in section
    assert "1 & 30 & $n \\le 10$ & 0 \\\\" in section
    assert "без ограничений \\& 100\\%" in section
    assert "2 & 70 &" in section and "& 0, 1 \\\\" in section


def test_plan_from_snapshot():
    snapshot = {
        "tests": [
            {"index": 1, "group": "0", "points": 0, "useInStatements": True},
            {"index": 2, "group": "1", "points": 0, "useInStatements": False},
            {"index": 3, "group": "1", "points": 40, "useInStatements": False},
        ],
        "groups": [{"name": "1", "dependencies": ["0"]}],
    }
    plan = plan_from_snapshot(snapshot)
    assert plan is not None
    assert plan["groups"][0]["samples"] is True
    assert plan["groups"][1] == {
        "name": "1", "points": 40.0, "description": "", "dependencies": ["0"], "samples": False,
        "generator": "gen_1", "cases": [{"args": "", "count": 2}],
    }
    assert plan_from_snapshot({"tests": []}) is None


def test_plan_validation_edge_cases():
    with pytest.raises(PlanError, match="хотя бы одна группа"):
        normalize_plan({"groups": [{"name": "0", "samples": True}]})
    for bad in ("nan", "inf", float("inf")):
        raw = {"groups": [{"name": "1", "points": bad, "cases": [{"args": "", "count": 1}]}]}
        with pytest.raises(PlanError, match="конечным|числом"):
            normalize_plan(raw)


def test_script_comment_cannot_break_freemarker():
    plan = normalize_plan({"groups": [{"name": "1", "description": "n --> m ${x} <#if>",
                                       "cases": [{"args": "1", "count": 2}]}]})
    script = build_script(plan)
    comment = script.splitlines()[1]
    assert "-->" not in comment[4:-4] and "${" not in comment and "<#" not in comment[4:]
    assert len(expand_freemarker(script)) == 2


def test_dependencies_on_empty_samples_group_are_dropped():
    plan = normalize_plan(PLAN)
    lines = expand_lines(plan)
    tests = [{"index": 1 + i, "manual": False} for i in range(len(lines))]
    a = assign(plan, tests, lines)
    assert a.policies["1"][2] == [] and a.policies["2"][2] == ["1"]
    assert any("убрана зависимость" in w for w in a.warnings)
