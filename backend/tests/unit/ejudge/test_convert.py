"""Polygon package parsing, serve.cfg editing and the conversion to ejudge."""
import pytest

from api.user.ejudge.common import EjudgeError
from api.user.ejudge.convert import MANAGED_KEYS, build_plan, memory_size, render_valuer
from api.user.ejudge.package import parse_package
from api.user.ejudge.servecfg import ServeCfg, render_value, unquote
from tests.unit.ejudge.helpers import SERVE_CFG, package_zip

GROUPED_TESTS: list[dict] = [
    {"group": "0", "points": 0, "sample": True},
    {"group": "0", "points": 0, "sample": True},
    *[{"group": "1", "points": 0}] * 3, {"group": "1", "points": 30},
    {"group": "2", "points": 0}, {"group": "2", "points": 70},
]
GROUPS: list[dict] = [
    {"name": "0", "feedback": "complete"},
    {"name": "1", "deps": ["0"]},
    {"name": "2", "deps": ["0", "1"]},
]


def plan_for(tests, groups=None, cfg_text=SERVE_CFG, **kwargs):
    return build_plan(parse_package(package_zip(tests, groups)), ServeCfg(cfg_text), polygon_id=555, **kwargs)


# --------------------------------------------------------------------------- package
def test_parse_package_reads_everything():
    pkg = parse_package(package_zip(GROUPED_TESTS, GROUPS, input_file="input.txt", time_limit=1500))
    assert pkg.short_name == "a-plus-b" and pkg.revision == 7
    assert pkg.name("english") == "Sum" and pkg.name("russian") == "Сумма"
    assert pkg.input_file == "input.txt" and pkg.output_file == ""
    assert pkg.time_limit_ms == 1500 and pkg.memory_limit_bytes == 256 * 1024 * 1024
    assert [t.group for t in pkg.tests] == ["0", "0", "1", "1", "1", "1", "2", "2"]
    assert pkg.tests[5].points == 30 and pkg.tests[0].sample
    assert pkg.tests[0].input == b"input 1\n" and pkg.tests[0].answer == b"answer 1\n"
    assert pkg.groups[2].dependencies == ["0", "1"] and pkg.groups[0].feedback_policy == "complete"
    assert pkg.checker_name == "std::ncmp.cpp" and pkg.checker_source[0] == "check.cpp"
    assert set(pkg.resources) == {"testlib.h", "olymp.sty"}
    assert pkg.has_groups and pkg.has_points


def test_parse_package_requires_full_package():
    with pytest.raises(EjudgeError, match="полный пакет"):
        parse_package(package_zip([{}], answers=False))
    with pytest.raises(EjudgeError, match="zip"):
        parse_package(b"not a zip")
    # interactive problems may have no answers
    assert parse_package(package_zip([{}], answers=False, interactor=True)).tests[0].answer is None


# --------------------------------------------------------------------------- serve.cfg
def test_servecfg_reads_and_edits_in_place():
    cfg = ServeCfg(SERVE_CFG.replace("\n", "\r\n"))
    assert cfg.score_system == "olympiad" and cfg.advanced_layout
    assert [s.values.get("short_name") for s in cfg.concrete_problems()] == ["A"]
    assert cfg.abstract_problems()[0].values["short_name"] == "Generic"
    assert cfg.next_problem_id() == 2 and cfg.free_short_name() == "B" and cfg.free_short_name("Z") == "Z"

    old = cfg.find_problem(problem_id=1)
    cfg.upsert_problem(old, {"id": 1, "short_name": "A", "long_name": 'Новая "задача"', "use_stdin": True})
    cfg.upsert_problem(None, {"id": 2, "short_name": "B", "max_vm_size": memory_size(512 * 2**20)})
    cfg.set_global("separate_user_score", 1)
    text = cfg.text()
    assert "\r\n" in text and text.count("[problem]") == 3
    assert 'long_name = "Новая \\"задача\\""' in text and "Old problem" not in text
    assert "max_vm_size = 512M" in text
    assert "separate_user_score = 1\r\n" in text
    assert "score_system = olympiad # olympiad scoring" in text  # comments are kept
    reparsed = ServeCfg(text)
    assert reparsed.find_problem(problem_id=1).values["long_name"] == 'Новая "задача"'
    assert reparsed.globals["separate_user_score"] == "1"


def test_values():
    assert render_value(True) == "1" and render_value(30.0) == "30" and render_value("a\\b") == '"a\\\\b"'
    assert unquote('"x \\"y\\""') == 'x "y"'
    assert memory_size(1024 * 2**20) == "1G" and memory_size(256 * 2**20) == "256M"


# --------------------------------------------------------------------------- conversion
def test_olympiad_groups_become_valuer_cfg():
    plan = plan_for(GROUPED_TESTS, GROUPS)
    assert plan.problem_id == 2 and plan.short_name == "B" and plan.internal_name == "a-plus-b"
    s = plan.section
    assert s["super"] == "Generic" and s["extid"] == "polygon:555"
    assert s["use_stdin"] is True and s["test_pat"] == "%03d.dat" and s["corr_pat"] == "%03d.ans"
    assert s["time_limit"] == 1 and s["real_time_limit"] == 5 and s["max_vm_size"] == "256M"
    assert s["full_score"] == 100 and s["full_user_score"] == 100
    assert s["test_score_list"] == "0 0 0 0 0 30 0 70"
    assert s["open_tests"] == "1-2:full, 3-6:brief, 7-8:brief"
    assert s["valuer_cmd"] == "gvaluer" and s["interactive_valuer"] is True
    assert plan.valuer_cfg == (
        "global {\n    stat_to_judges 1;\n    stat_to_users 0;\n}\n\n"
        "group 0 {\n    tests 1-2;\n    score 0;\n}\n\n"
        "group 1 {\n    tests 3-6;\n    score 30;\n    requires 0;\n}\n\n"
        "group 2 {\n    tests 7-8;\n    score 70;\n    requires 0, 1;\n    sets_marked_if_passed 0, 1, 2;\n}\n"
    )
    assert plan.compile == [("check", "check.cpp"), ("gvaluer", "gvaluer.cpp")]
    assert {"tests/001.dat", "tests/008.ans", "check.cpp", "testlib.h", "valuer.cfg", "gvaluer.cpp",
            "problem.cfg"} <= set(plan.files)
    assert plan.contest_globals == {"separate_user_score": 1}
    assert "long_name_en = \"Sum\"" in plan.problem_cfg and "revision = 7" in plan.problem_cfg
    assert not plan.renumbered


def test_interleaved_groups_are_renumbered():
    tests = [{"group": "1", "points": 0}, {"group": "2", "points": 0}, {"group": "1", "points": 40},
             {"group": "2", "points": 60}]
    plan = plan_for(tests, [{"name": "1"}, {"name": "2", "deps": ["1"]}])
    assert plan.renumbered and "перенумерованы" in plan.warnings[0]
    assert plan.files["tests/002.dat"] == b"input 3\n"  # old test 3 is now test 2
    assert plan.files["tests/003.ans"] == b"answer 2\n"
    assert [(g.first, g.last, g.score) for g in plan.groups] == [(1, 2, 40), (3, 4, 60)]


def test_each_test_and_hidden_groups():
    tests = [{"group": "1", "points": 10}] * 3 + [{"group": "2", "points": 0}, {"group": "2", "points": 70}]
    plan = plan_for(tests, [{"name": "1", "policy": "each-test", "feedback": "points"},
                            {"name": "2", "feedback": "none"}])
    assert "test_score 10;" in plan.valuer_cfg and "offline;" in plan.valuer_cfg
    assert "sets_marked_if_passed 1;" in plan.valuer_cfg
    assert plan.section["full_score"] == 100 and plan.section["full_user_score"] == 30
    assert plan.section["test_score_list"] == "10 10 10 0 70"
    assert plan.section["open_tests"] == "1-3:brief, 4-5:hidden"


def test_acm_contest_ignores_scoring():
    plan = plan_for(GROUPED_TESTS, GROUPS, cfg_text=SERVE_CFG.replace("olympiad", "acm"))
    assert plan.valuer_cfg is None and "full_score" not in plan.section
    assert plan.compile == [("check", "check.cpp")]
    assert any("ACM" in w for w in plan.warnings)
    assert plan.contest_globals == {}


def test_no_groups_cases():
    per_test = plan_for([{"points": 40}, {"points": 60}])
    assert per_test.valuer_cfg is None and per_test.section["test_score_list"] == "40 60"
    assert per_test.section["full_score"] == 100
    nothing = plan_for([{}, {}, {}])
    assert "tests 1-3;" in nothing.valuer_cfg and "score 100;" in nothing.valuer_cfg
    assert any("одна группа на 100" in w for w in nothing.warnings)


def test_existing_problem_is_updated_and_names_respected():
    cfg = SERVE_CFG + '\n[problem]\nid = 5\nshort_name = "E"\ninternal_name = "a-plus-b"\nextid = "polygon:555"\n'
    plan = plan_for([{}], cfg_text=cfg)
    assert plan.problem_id == 5 and plan.short_name == "E"
    assert any("будет обновлена" in w for w in plan.warnings)
    taken = plan_for([{}], short_name="A", internal_name="custom")
    assert taken.short_name == "B" and taken.internal_name == "custom"


def test_conversion_errors():
    with pytest.raises(EjudgeError, match="advanced_layout"):
        plan_for([{}], cfg_text=SERVE_CFG.replace("advanced_layout\n", ""))
    with pytest.raises(EjudgeError, match="нет группы"):
        plan_for([{"group": "1"}, {}], [{"name": "1"}])
    with pytest.raises(EjudgeError, match="несуществующей"):
        plan_for([{"group": "1", "points": 5}], [{"name": "1", "deps": ["9"]}])


def test_interactor_and_files():
    pkg = parse_package(package_zip([{}], interactor=True, answers=False, input_file="in.txt"))
    plan = build_plan(pkg, ServeCfg(SERVE_CFG.replace("olympiad", "acm")), polygon_id=1)
    assert plan.section["interactor_cmd"] == "interactor" and plan.section["use_corr"] is False
    assert "corr_pat" not in plan.section and plan.section["input_file"] == "in.txt"
    assert ("interactor", "interactor.cpp") in plan.compile


def test_render_valuer_without_online_groups():
    from api.user.ejudge.convert import ValuerGroup
    text = render_valuer([ValuerGroup("1", 1, 2, 50, False, [], "hidden")])
    assert "sets_marked_if_passed" not in text and "offline;" in text


def test_upsert_merges_into_existing_section():
    text = SERVE_CFG + 'max_core_size = 0 # site setting\ntime_limit = 2\nvaluer_cmd = "old"\n# trailing note\n\n[language]\nid = 4\n'
    cfg = ServeCfg(text)
    old = cfg.find_problem(problem_id=1)
    cfg.upsert_problem(old, {"id": 1, "short_name": "A", "time_limit_millis": 1500, "long_name": "New"}, MANAGED_KEYS)
    out = cfg.text()
    block = out.split("[problem]")[2].split("[language]")[0]
    assert 'super = "Generic"' in block and "max_core_size = 0 # site setting" in block
    assert "# trailing note" in block and 'long_name = "New"' in block and "Old problem" not in block
    assert "time_limit = 2" not in block and "valuer_cmd" not in block and "time_limit_millis = 1500" in block
    assert out.count("[language]") == 2 and ServeCfg(out).find_problem(problem_id=1).values["long_name"] == "New"


def test_group_ordering_and_names():
    # offline group first in Polygon order goes last; dependency on an empty group is dropped
    tests = [{"group": "hidden", "points": 50}, {"group": "big one", "points": 50}]
    plan = plan_for(tests, [{"name": "hidden", "feedback": "none"}, {"name": "big one", "deps": ["empty"]},
                            {"name": "empty"}])
    assert [g.polygon_name for g in plan.groups] == ["big one", "hidden"]
    assert [g.name for g in plan.groups] == ["g0", "hidden"]
    assert any("без тестов убрана" in w for w in plan.warnings)
    assert any("называется g0" in w for w in plan.warnings)
    assert "group g0 {" in plan.valuer_cfg and plan.files["tests/001.dat"] == b"input 2\n"

    with pytest.raises(EjudgeError, match="offline"):
        plan_for([{"group": "1", "points": 50}, {"group": "2", "points": 50}],
                 [{"name": "1", "feedback": "none"}, {"name": "2", "deps": ["1"]}])
    with pytest.raises(EjudgeError, match="циклические"):
        plan_for([{"group": "1", "points": 50}, {"group": "2", "points": 50}],
                 [{"name": "1", "deps": ["2"]}, {"name": "2", "deps": ["1"]}])
    with pytest.raises(EjudgeError, match="дробные"):
        plan_for([{"group": "1", "points": 0.5}], [{"name": "1"}])
    with pytest.raises(EjudgeError, match="дробные"):
        plan_for([{"points": 0.5}, {"points": 1}])


def test_only_own_problem_is_updated_and_names_are_unique():
    # a problem that merely shares the directory name is not ours: a new id and directory are used
    cfg = SERVE_CFG + '\n[problem]\nid = 5\nshort_name = "E"\ninternal_name = "a-plus-b"\n'
    plan = plan_for([{}], cfg_text=cfg)
    assert plan.problem_id == 6 and plan.internal_name == "a-plus-b-2"
    assert any("занят другой задачей" in w for w in plan.warnings)
    # updating our problem keeps its letter unless it was taken by another one
    ours = SERVE_CFG + '\n[problem]\nid = 5\nshort_name = "A"\ninternal_name = "x"\nextid = "polygon:555"\n'
    plan = plan_for([{}], cfg_text=ours)
    assert plan.problem_id == 5 and plan.internal_name == "x" and plan.short_name == "B"
    # an explicit id of a foreign problem replaces it with a warning
    foreign = SERVE_CFG.replace('internal_name = "old"', 'internal_name = "old"\nextid = "polygon:9"')
    plan = plan_for([{}], cfg_text=foreign, problem_id=1)
    assert plan.problem_id == 1 and plan.short_name == "A"
    assert any("polygon:9" in w for w in plan.warnings)


def test_package_limits_and_languages(monkeypatch):
    from api.user.ejudge import package as package_module
    data = package_zip([{}])
    monkeypatch.setattr(package_module, "MAX_UNPACKED_BYTES", 10)
    with pytest.raises(EjudgeError, match="2 ГБ"):
        parse_package(data)
    monkeypatch.undo()
    with pytest.raises(EjudgeError, match="только исходники на C\\+\\+"):
        parse_package(_rewrite(data, "problem.xml", lambda x: x.replace(
            b'type="cpp.g++17"/></checker>', b'type="java.11"/></checker>')))


def _rewrite(data: bytes, name: str, change) -> bytes:
    import io
    import zipfile
    out = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(data)) as src, zipfile.ZipFile(out, "w") as dst:
        for info in src.infolist():
            content = src.read(info.filename)
            dst.writestr(info.filename, change(content) if info.filename == name else content)
    return out.getvalue()
