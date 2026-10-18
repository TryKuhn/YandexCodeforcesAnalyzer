"""Reading a Polygon package (``problem.xml`` + files) into plain data.

Only what the Ejudge export needs: names, limits, I/O files, the testset (tests
with groups and points, group policies and dependencies), checker, interactor
and resource files. A *full* package is required: generated tests and their
answers are taken from it, nothing is regenerated here.
"""
from __future__ import annotations

import io
import posixpath
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field

from api.user.ejudge.common import EjudgeError

MAX_PACKAGE_BYTES = 1024 * 1024 * 1024
MAX_UNPACKED_BYTES = 2 * 1024 * 1024 * 1024


@dataclass
class PackageTest:
    index: int  # 1-based, Polygon order
    group: str | None
    points: float
    sample: bool
    input: bytes
    answer: bytes | None


@dataclass
class PackageGroup:
    name: str
    points_policy: str  # complete-group | each-test
    feedback_policy: str  # none | points | icpc | complete
    dependencies: list[str] = field(default_factory=list)


@dataclass
class PolygonPackage:
    short_name: str
    revision: int | None
    names: dict[str, str]
    input_file: str  # "" = stdin
    output_file: str  # "" = stdout
    time_limit_ms: int
    memory_limit_bytes: int
    tests: list[PackageTest]
    groups: list[PackageGroup]
    checker_name: str | None
    checker_source: tuple[str, bytes] | None  # (file name, content)
    interactor_source: tuple[str, bytes] | None
    resources: dict[str, bytes]  # name -> content (testlib.h, ...)

    @property
    def has_points(self) -> bool:
        return any(t.points for t in self.tests)

    @property
    def has_groups(self) -> bool:
        return any(t.group is not None for t in self.tests)

    def name(self, *languages: str) -> str:
        for lang in languages:
            if self.names.get(lang):
                return self.names[lang]
        return next(iter(self.names.values()), self.short_name)


def _float(value: str | None) -> float:
    try:
        return float(value) if value not in (None, "") else 0.0
    except ValueError:
        return 0.0


def _read(zf: zipfile.ZipFile, path: str) -> bytes | None:
    path = posixpath.normpath(path).lstrip("/")
    try:
        return zf.read(path)
    except KeyError:
        return None


def parse_package(data: bytes, *, testset: str = "tests") -> PolygonPackage:
    """Parse a package archive; :class:`EjudgeError` when it is unusable."""
    if len(data) > MAX_PACKAGE_BYTES:
        raise EjudgeError("пакет больше 1 ГБ")
    try:
        zf = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        raise EjudgeError("пакет Polygon не является zip-архивом")

    with zf:
        if sum(info.file_size for info in zf.infolist()) > MAX_UNPACKED_BYTES:
            raise EjudgeError("распакованный пакет больше 2 ГБ")
        raw_xml = _read(zf, "problem.xml")
        if raw_xml is None:
            raise EjudgeError("в пакете нет problem.xml")
        try:
            root = ET.fromstring(raw_xml)
        except ET.ParseError as e:
            raise EjudgeError(f"problem.xml не разбирается: {e}")

        names = {
            n.get("language", ""): n.get("value", "")
            for n in root.findall("./names/name")
        }
        judging = root.find("judging")
        if judging is None:
            raise EjudgeError("в problem.xml нет раздела judging")
        ts = next((t for t in judging.findall("testset") if t.get("name") == testset), None)
        if ts is None:
            raise EjudgeError(f"в пакете нет набора тестов {testset!r}")

        time_limit = int(_float(ts.findtext("time-limit")) or 1000)
        memory_limit = int(_float(ts.findtext("memory-limit")) or 256 * 1024 * 1024)
        input_pattern = ts.findtext("input-path-pattern") or "tests/%02d"
        answer_pattern = ts.findtext("answer-path-pattern") or "tests/%02d.a"

        tests: list[PackageTest] = []
        missing_answers = 0
        for i, node in enumerate(ts.findall("./tests/test"), start=1):
            content = _read(zf, input_pattern % i)
            if content is None:
                raise EjudgeError(
                    f"в пакете нет входных данных теста {i}: нужен полный пакет (full) с тестами"
                )
            answer = _read(zf, answer_pattern % i)
            if answer is None:
                missing_answers += 1
            tests.append(PackageTest(
                index=i,
                group=node.get("group"),
                points=_float(node.get("points")),
                sample=node.get("sample") == "true",
                input=content,
                answer=answer,
            ))
        if not tests:
            raise EjudgeError("в пакете нет тестов")

        groups = [
            PackageGroup(
                name=g.get("name", ""),
                points_policy=(g.get("points-policy") or "complete-group").lower(),
                feedback_policy=(g.get("feedback-policy") or "complete").lower(),
                dependencies=[d.get("group", "") for d in g.findall("./dependencies/dependency")],
            )
            for g in ts.findall("./groups/group")
        ]

        interactor_node = root.find("./assets/interactor/source")
        interactive = interactor_node is not None
        if missing_answers and not interactive:
            raise EjudgeError(f"в пакете нет ответов для {missing_answers} тестов: соберите полный пакет")

        def source(node: ET.Element | None) -> tuple[str, bytes] | None:
            if node is None or not node.get("path"):
                return None
            path = node.get("path", "")
            kind = node.get("type") or ""
            if kind and not kind.startswith("cpp."):
                # ejudge compiles the checker/interactor with EJUDGE_CXX on the server
                raise EjudgeError(f"{posixpath.basename(path)}: поддерживаются только исходники на C++ (тип {kind})")
            content = _read(zf, path)
            if content is None:
                raise EjudgeError(f"в пакете нет файла {path}")
            return posixpath.basename(path), content

        checker = root.find("./assets/checker")
        resources: dict[str, bytes] = {}
        for res in root.findall("./files/resources/file"):
            path = res.get("path", "")
            content = _read(zf, path)
            if content is not None:
                resources[posixpath.basename(path)] = content

        revision = root.get("revision")
        return PolygonPackage(
            short_name=root.get("short-name") or "problem",
            revision=int(revision) if revision and revision.isdigit() else None,
            names=names,
            input_file=judging.get("input-file") or "",
            output_file=judging.get("output-file") or "",
            time_limit_ms=time_limit,
            memory_limit_bytes=memory_limit,
            tests=tests,
            groups=groups,
            checker_name=checker.get("name") if checker is not None else None,
            checker_source=source(checker.find("source") if checker is not None else None),
            interactor_source=source(interactor_node),
            resources=resources,
        )
