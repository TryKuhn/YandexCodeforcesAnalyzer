"""Polygon package layout, as a plugin like any other.

Polygon stores a problem as problem.xml plus tests/NN and tests/NN.a, with the
checker in check.cpp. We read and write that shape so a problem can leave for
Polygon and come back without going through their API.
"""
import xml.etree.ElementTree as ElementTree
import zipfile
from io import BytesIO

from .base import Package, PackageError, PackageFormat, PackageTest

_MANIFEST = "problem.xml"
_CHECKER = "check.cpp"

# Polygon keeps limits in bytes and milliseconds
_MB = 1024 * 1024


class PolygonFormat(PackageFormat):
    name = "polygon"

    def export(self, package: Package) -> bytes:
        problem = ElementTree.Element("problem", {"short-name": package.name})
        judging = ElementTree.SubElement(problem, "judging")
        testset = ElementTree.SubElement(judging, "testset", {"name": "tests"})

        ElementTree.SubElement(testset, "time-limit").text = str(package.time_limit_ms)
        ElementTree.SubElement(testset, "memory-limit").text = str(
            package.memory_limit_mb * _MB
        )
        ElementTree.SubElement(testset, "test-count").text = str(len(package.tests))
        ElementTree.SubElement(testset, "input-path-pattern").text = "tests/%02d"
        ElementTree.SubElement(testset, "answer-path-pattern").text = "tests/%02d.a"

        tests_node = ElementTree.SubElement(testset, "tests")
        for test in package.tests:
            attributes = {"method": "manual"}
            if test.is_sample:
                attributes["sample"] = "true"
            if test.points:
                attributes["points"] = str(test.points)
            if test.group:
                attributes["group"] = test.group
            ElementTree.SubElement(tests_node, "test", attributes)

        if any(test.group for test in package.tests):
            groups_node = ElementTree.SubElement(testset, "groups")
            seen: dict[str, float] = {}
            for test in package.tests:
                if test.group:
                    seen[test.group] = seen.get(test.group, 0.0) + test.points
            for group, points in seen.items():
                ElementTree.SubElement(
                    groups_node,
                    "group",
                    {"name": group, "points": str(points), "feedback-policy": "complete"},
                )

        assets = ElementTree.SubElement(problem, "assets")
        checker_node = ElementTree.SubElement(assets, "checker", {"type": "testlib"})
        source = ElementTree.SubElement(checker_node, "source")
        source.set("path", _CHECKER)
        source.set("type", "cpp.g++17")

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                _MANIFEST, ElementTree.tostring(problem, encoding="unicode")
            )
            archive.writestr(_CHECKER, package.checker)
            for test in package.tests:
                archive.writestr(f"tests/{test.index:02d}", test.input_data)
                archive.writestr(f"tests/{test.index:02d}.a", test.answer_data)
            for name, data in package.files.items():
                archive.writestr(f"files/{name}", data)
        return buffer.getvalue()

    def materialize(self, archive: bytes) -> Package:
        try:
            with zipfile.ZipFile(BytesIO(archive)) as zip_file:
                names = set(zip_file.namelist())
                if _MANIFEST not in names:
                    raise PackageError(f"{_MANIFEST} is missing")

                problem = ElementTree.fromstring(zip_file.read(_MANIFEST).decode())
                testset = problem.find("./judging/testset")
                if testset is None:
                    raise PackageError("problem.xml has no testset")

                time_limit = testset.findtext("time-limit", "1000")
                memory_limit = testset.findtext("memory-limit", str(256 * _MB))

                tests = []
                for index, node in enumerate(testset.findall("./tests/test"), start=1):
                    tests.append(
                        PackageTest(
                            index=index,
                            input_data=zip_file.read(f"tests/{index:02d}"),
                            answer_data=zip_file.read(f"tests/{index:02d}.a"),
                            group=node.get("group"),
                            points=float(node.get("points", 0) or 0),
                            is_sample=node.get("sample") == "true",
                        )
                    )

                files = {
                    name[len("files/"):]: zip_file.read(name)
                    for name in names
                    if name.startswith("files/") and not name.endswith("/")
                }

                return Package(
                    name=problem.get("short-name", "imported"),
                    tests=tests,
                    checker=zip_file.read(_CHECKER) if _CHECKER in names else b"",
                    time_limit_ms=int(time_limit),
                    memory_limit_mb=max(1, int(memory_limit) // _MB),
                    files=files,
                )
        except zipfile.BadZipFile as exc:
            raise PackageError("not a zip archive") from exc
        except ElementTree.ParseError as exc:
            raise PackageError(f"problem.xml is malformed: {exc}") from exc
        except KeyError as exc:
            raise PackageError(f"archive is incomplete: {exc}") from exc
