"""Polygon package -> ejudge problem directory, ``[problem]`` section and ``valuer.cfg``.

Scoring:

* ``acm`` contests: groups and points are ignored, ejudge stops at the first
  failed test anyway;
* ``olympiad`` / ``kirov`` / ``moscow``: groups become ``valuer.cfg`` for
  ejudge's ``gvaluer`` (compiled into the problem directory):

  - Polygon ``complete-group`` -> ``score S`` (S = sum of the group's test
    points), ``each-test`` -> ``test_score X``;
  - dependencies -> ``requires``;
  - ``icpc``/``complete`` feedback: gvaluer stops a group at its first failure,
    exactly like Polygon's first-failed groups;
  - feedback ``none`` -> an ``offline`` group (results hidden until the end),
    ``points``/``icpc`` -> ``brief``, ``complete`` -> ``full`` in ``open_tests``.

  gvaluer needs every group to be a contiguous range of tests, so tests are
  renumbered (groups in order of first appearance) when Polygon interleaves them.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from api.user.ejudge.common import EjudgeError
from api.user.ejudge.package import PackageGroup, PackageTest, PolygonPackage
from api.user.ejudge.servecfg import ServeCfg, Unquoted, render_section

TEST_PAT = "%03d.dat"
CORR_PAT = "%03d.ans"
GVALUER_SOURCE = Path(__file__).parent / "assets" / "gvaluer.cpp"
ACM_SYSTEMS = ("acm",)

# [problem] keys the export owns: on update they are rewritten or, when no longer
# produced, removed; any other key of an existing section is left alone
MANAGED_KEYS = frozenset({
    "short_name", "long_name", "internal_name", "extid", "use_stdin", "use_stdout", "input_file",
    "output_file", "test_pat", "use_corr", "corr_pat", "time_limit", "time_limit_millis", "real_time_limit",
    "max_vm_size", "max_stack_size", "check_cmd", "standard_checker", "enable_testlib_mode", "interactor_cmd",
    "full_score", "full_user_score", "test_score", "test_score_list", "score_tests", "open_tests",
    "final_open_tests", "valuer_cmd", "interactive_valuer", "valuer_sets_marked", "olympiad_mode", "run_penalty",
})
FEEDBACK = {"none": "hidden", "points": "brief", "icpc": "brief", "complete": "full"}
_INTERNAL_RE = re.compile(r"[^a-z0-9_-]+")


@dataclass
class ValuerGroup:
    name: str
    first: int
    last: int
    score: float
    each_test: bool
    requires: list[str]
    feedback: str  # hidden | brief | full
    polygon_name: str = ""


@dataclass
class ExportPlan:
    internal_name: str
    problem_id: int
    short_name: str
    files: dict[str, bytes]  # relative to the problem directory
    compile: list[tuple[str, str]]  # (executable, source) in the problem directory
    section: dict[str, object]  # the [problem] section of serve.cfg
    problem_cfg: str
    valuer_cfg: str | None
    groups: list[ValuerGroup]
    renumbered: bool
    score_system: str
    contest_globals: dict[str, object] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def report(self) -> dict:
        return {
            "internal_name": self.internal_name,
            "problem_id": self.problem_id,
            "short_name": self.short_name,
            "score_system": self.score_system,
            "tests": sum(1 for f in self.files if f.startswith("tests/") and f.endswith(".dat")),
            "groups": [
                {"name": g.polygon_name or g.name, "tests": f"{g.first}-{g.last}", "score": g.score,
                 "each_test": g.each_test, "requires": g.requires, "feedback": g.feedback}
                for g in self.groups
            ],
            "renumbered": self.renumbered,
            "problem_cfg": self.problem_cfg,
            "valuer_cfg": self.valuer_cfg,
            "section": {k: str(v) for k, v in self.section.items()},
            "contest_globals": {k: str(v) for k, v in self.contest_globals.items()},
            "warnings": self.warnings,
        }


def _num(value: float) -> int | float:
    return int(value) if float(value).is_integer() else value


def memory_size(limit_bytes: int) -> Unquoted:
    mb = max(1, limit_bytes // (1024 * 1024))
    if mb % 1024 == 0:
        return Unquoted(f"{mb // 1024}G")
    return Unquoted(f"{mb}M")


def internal_name_for(package: PolygonPackage, polygon_id: int) -> str:
    name = _INTERNAL_RE.sub("-", package.short_name.lower()).strip("-")
    return name or f"polygon-{polygon_id}"


_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,32}$")


def _feedback(policy: PackageGroup | None) -> str:
    return FEEDBACK.get(policy.feedback_policy, "brief") if policy else "full"


def group_order(package: PolygonPackage, warnings: list[str]) -> tuple[list[str], dict[str, list[str]]]:
    """Groups in the order gvaluer accepts, with their (cleaned) dependencies.

    gvaluer needs every required group BEFORE the group and all offline groups
    AFTER all online ones; within that, Polygon's order of first appearance is kept.
    """
    appearance: list[str] = []
    for t in package.tests:
        if t.group not in appearance:
            appearance.append(t.group or "")
    policies = {g.name: g for g in package.groups}
    offline = {name: _feedback(policies.get(name)) == "hidden" for name in appearance}

    deps: dict[str, list[str]] = {}
    for name in appearance:
        policy = policies.get(name)
        cleaned = []
        for dep in (policy.dependencies if policy else []):
            if dep in offline:
                cleaned.append(dep)
            elif dep in policies:
                warnings.append(f"группа {name}: зависимость от группы {dep} без тестов убрана")
            else:
                raise EjudgeError(f"группа {name} зависит от несуществующей группы {dep}")
        deps[name] = cleaned
        if not offline[name] and any(offline[d] for d in cleaned):
            raise EjudgeError(
                f"группа {name} с видимыми результатами зависит от группы без обратной связи — "
                "gvaluer требует, чтобы offline-группы шли последними"
            )

    ordered: list[str] = []
    remaining = list(appearance)
    while remaining:
        ready = [g for g in remaining if all(d in ordered for d in deps[g])]
        if not ready:
            raise EjudgeError(f"циклические зависимости групп: {', '.join(remaining)}")
        pick = min(ready, key=lambda g: (offline[g], appearance.index(g)))
        ordered.append(pick)
        remaining.remove(pick)
    return ordered, deps


def order_tests(package: PolygonPackage, order: list[str] | None = None) -> tuple[list[PackageTest], bool]:
    """Tests with every group contiguous, groups in ``order`` (stable within a group)."""
    if not package.has_groups:
        return list(package.tests), False
    missing = [t.index for t in package.tests if t.group is None]
    if missing:
        raise EjudgeError(f"у тестов {missing[:10]} нет группы, а у остальных есть")
    if order is None:
        order = list(dict.fromkeys(t.group or "" for t in package.tests))
    ordered = sorted(package.tests, key=lambda t: (order.index(t.group or ""), t.index))
    return ordered, [t.index for t in ordered] != [t.index for t in package.tests]


def _integer_points(values: list[float], where: str) -> None:
    bad = sorted({v for v in values if not float(v).is_integer()})
    if bad:
        raise EjudgeError(f"{where}: дробные баллы {bad[:5]} — ejudge принимает только целые")


def valuer_groups(
    package: PolygonPackage, tests: list[PackageTest], warnings: list[str],
    order: list[str] | None = None, deps: dict[str, list[str]] | None = None,
) -> list[ValuerGroup]:
    """Groups over the renumbered tests (1-based positions in ``tests``)."""
    if not package.has_groups:
        if package.has_points:
            _integer_points([t.points for t in tests], "баллы тестов")
            return []  # per-test points: test_score_list, no valuer needed
        warnings.append("в задаче нет групп и баллов: вся задача — одна группа на 100 баллов")
        return [ValuerGroup("0", 1, len(tests), 100, False, [], "brief")]

    if order is None or deps is None:
        order, deps = group_order(package, warnings)
    policies: dict[str, PackageGroup] = {g.name: g for g in package.groups}
    # gvaluer tokenizes names as [A-Za-z0-9_]; other Polygon names get g<N>
    safe = {name: name if _SAFE_NAME_RE.match(name) else f"g{i}" for i, name in enumerate(order)}
    taken = [n for n in safe.values()]
    if len(set(taken)) != len(taken):
        safe = {name: f"g{i}" for i, name in enumerate(order)}
    for name, valuer_name in safe.items():
        if name != valuer_name:
            warnings.append(f"группа «{name}» в valuer.cfg называется {valuer_name}")

    result: list[ValuerGroup] = []
    position = 0
    for name in order:
        members = [t for t in tests if (t.group or "") == name]
        first, last = position + 1, position + len(members)
        position = last
        policy = policies.get(name) or PackageGroup(name, "complete-group", "complete")
        each_test = policy.points_policy == "each-test"
        points = [t.points for t in members]
        _integer_points(points, f"группа {name}")
        if each_test:
            if len(set(points)) > 1:
                warnings.append(
                    f"группа {name}: баллы тестов различаются ({sorted(set(points))}), gvaluer поддерживает "
                    f"одинаковые — взято {max(points):g} за тест"
                )
            score = max(points)
        else:
            score = sum(points)
        result.append(ValuerGroup(
            name=safe[name], first=first, last=last, score=score, each_test=each_test,
            requires=[safe[d] for d in deps[name]], feedback=_feedback(policies.get(name)),
            polygon_name=name,
        ))
    return result


def render_valuer(groups: list[ValuerGroup]) -> str:
    lines = ["global {", "    stat_to_judges 1;", "    stat_to_users 0;", "}", ""]
    online = [g.name for g in groups if g.feedback != "hidden"]
    for g in groups:
        lines.append(f"group {g.name} {{")
        lines.append(f"    tests {g.first}-{g.last};")
        lines.append(f"    {'test_score' if g.each_test else 'score'} {_num(g.score)};")
        if g.requires:
            lines.append(f"    requires {', '.join(g.requires)};")
        if online and g.name == online[-1] and g.feedback != "hidden":
            lines.append(f"    sets_marked_if_passed {', '.join(online)};")
        if g.feedback == "hidden":
            lines.append("    offline;")
        lines.append("}")
        lines.append("")
    return "\n".join(lines)


def test_score_list(groups: list[ValuerGroup], tests: list[PackageTest]) -> str:
    if not groups:
        return " ".join(str(_num(t.points)) for t in tests)
    scores: list[str] = []
    for g in groups:
        size = g.last - g.first + 1
        if g.each_test:
            scores += [str(_num(g.score))] * size
        else:
            scores += ["0"] * (size - 1) + [str(_num(g.score))]
    return " ".join(scores)


def build_plan(
    package: PolygonPackage,
    cfg: ServeCfg,
    *,
    polygon_id: int,
    short_name: str | None = None,
    problem_id: int | None = None,
    internal_name: str | None = None,
    gvaluer_binary: str = "",
) -> ExportPlan:
    """Everything the upload needs, computed locally (no I/O)."""
    if not cfg.advanced_layout:
        raise EjudgeError(
            "в serve.cfg контеста не включён advanced_layout: задачи ищутся в problems/<internal_name>, "
            "включите его в настройках контеста"
        )
    warnings: list[str] = []
    score_system = cfg.score_system
    extid = f"polygon:{polygon_id}"
    internal = internal_name or internal_name_for(package, polygon_id)

    # only our own problem (same extid) or an explicitly chosen id is updated;
    # a mere internal_name match may be an unrelated problem
    existing = cfg.find_problem(extid=extid, problem_id=problem_id)
    if existing is not None:
        problem_id = int(existing.values.get("id") or problem_id or cfg.next_problem_id())
        other_extid = existing.values.get("extid")
        if other_extid and other_extid != extid:
            warnings.append(f"задача id {problem_id} была импортирована из {other_extid} и будет заменена")
        current_short = existing.values.get("short_name")
        short = cfg.free_short_name(short_name or current_short, exclude=existing)
        internal = internal_name or existing.values.get("internal_name") or internal
        warnings.append(f"задача уже есть в контесте (id {problem_id}), она будет обновлена")
    else:
        problem_id = problem_id or cfg.next_problem_id()
        short = cfg.free_short_name(short_name)
    if short_name and short != short_name:
        warnings.append(f"короткое имя {short_name} занято, использовано {short}")
    free_internal = cfg.free_internal_name(internal, exclude=existing)
    if free_internal != internal:
        warnings.append(f"каталог {internal} занят другой задачей, использован {free_internal}")
        internal = free_internal

    order: list[str] | None = None
    deps: dict[str, list[str]] | None = None
    if score_system not in ACM_SYSTEMS and package.has_groups:
        order, deps = group_order(package, warnings)
        tests, renumbered = order_tests(package, order)
    else:
        tests, renumbered = list(package.tests), False
    if renumbered:
        warnings.append("тесты перенумерованы, чтобы каждая группа шла подряд (так требует gvaluer)")

    files: dict[str, bytes] = {}
    for position, test in enumerate(tests, start=1):
        files[f"tests/{TEST_PAT % position}"] = test.input
        if test.answer is not None:
            files[f"tests/{CORR_PAT % position}"] = test.answer
    has_answers = all(t.answer is not None for t in tests)

    for name, content in package.resources.items():
        files[name] = content

    compile_steps: list[tuple[str, str]] = []
    if package.checker_source is None:
        raise EjudgeError("в пакете нет исходника чекера")
    files["check.cpp"] = package.checker_source[1]
    compile_steps.append(("check", "check.cpp"))
    if package.interactor_source is not None:
        files["interactor.cpp"] = package.interactor_source[1]
        compile_steps.append(("interactor", "interactor.cpp"))

    tl = package.time_limit_ms
    memory = memory_size(package.memory_limit_bytes)
    section: dict[str, object] = {"id": problem_id}
    abstract = cfg.abstract_problems()
    if len(abstract) == 1 and abstract[0].values.get("short_name"):
        section["super"] = abstract[0].values["short_name"]
    section.update({
        "short_name": short,
        "long_name": package.name("russian", "english"),
        "internal_name": internal,
        "extid": extid,
        "use_stdin": not package.input_file,
        "use_stdout": not package.output_file,
    })
    if package.input_file:
        section["input_file"] = package.input_file
    if package.output_file:
        section["output_file"] = package.output_file
    section.update({
        "test_pat": TEST_PAT,
        "use_corr": has_answers,
    })
    if has_answers:
        section["corr_pat"] = CORR_PAT
    if tl % 1000 == 0:
        section["time_limit"] = tl // 1000
    else:
        section["time_limit_millis"] = tl
    section.update({
        "real_time_limit": max(5, (tl * 2 + 999) // 1000),
        "max_vm_size": memory,
        "max_stack_size": memory,
        "check_cmd": "check",
        "enable_testlib_mode": True,
    })
    if package.interactor_source is not None:
        section["interactor_cmd"] = "interactor"

    groups: list[ValuerGroup] = []
    valuer: str | None = None
    contest_globals: dict[str, object] = {}
    if score_system in ACM_SYSTEMS:
        if package.has_groups or package.has_points:
            warnings.append("контест ACM: группы и баллы Polygon не переносятся (тесты до первой ошибки)")
    else:
        groups = valuer_groups(package, tests, warnings, order, deps)
        full_score = sum(g.score * ((g.last - g.first + 1) if g.each_test else 1) for g in groups) \
            if groups else sum(t.points for t in tests)
        user_score = sum(g.score * ((g.last - g.first + 1) if g.each_test else 1)
                         for g in groups if g.feedback != "hidden") if groups else full_score
        section["full_score"] = _num(full_score)
        section["full_user_score"] = _num(user_score)
        section["test_score_list"] = test_score_list(groups, tests)
        if groups:
            section["open_tests"] = ", ".join(f"{g.first}-{g.last}:{g.feedback}" for g in groups)
            section["final_open_tests"] = ", ".join(f"{g.first}-{g.last}:full" for g in groups)
            valuer = render_valuer(groups)
            files["valuer.cfg"] = valuer.encode()
            section.update({
                "valuer_cmd": "gvaluer",
                "interactive_valuer": True,
                "valuer_sets_marked": True,
                "olympiad_mode": True,
                "run_penalty": 0,
            })
            if not gvaluer_binary:
                files["gvaluer.cpp"] = GVALUER_SOURCE.read_bytes()
                compile_steps.append(("gvaluer", "gvaluer.cpp"))
        if cfg.globals.get("separate_user_score", "0") in ("0", ""):
            contest_globals["separate_user_score"] = 1
        if full_score <= 0:
            warnings.append("сумма баллов задачи равна 0")

    problem_cfg_values = {**section, "long_name_en": package.name("english", "russian")}
    if package.revision is not None:
        problem_cfg_values["revision"] = package.revision
    problem_cfg = "# -*- coding: utf-8 -*-\n# generated from Polygon problem " \
        f"{polygon_id} by createmanager\n\n" + "\n".join(render_section("problem", problem_cfg_values)) + "\n"
    files["problem.cfg"] = problem_cfg.encode()

    return ExportPlan(
        internal_name=internal, problem_id=int(problem_id), short_name=short, files=files,
        compile=compile_steps, section=section, problem_cfg=problem_cfg, valuer_cfg=valuer, groups=groups,
        renumbered=renumbered, score_system=score_system, contest_globals=contest_globals, warnings=warnings,
    )
