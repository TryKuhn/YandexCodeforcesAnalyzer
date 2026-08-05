"""Our own package format: everything the judge knows, nothing lost."""
import json
import zipfile
from io import BytesIO

from .base import Package, PackageError, PackageFormat, PackageTest

_MANIFEST = "problem.json"
_CHECKER = "checker.cpp"
_VERSION = 1


class NativeFormat(PackageFormat):
    name = "native"

    def export(self, package: Package) -> bytes:
        manifest = {
            "version": _VERSION,
            "name": package.name,
            "time_limit_ms": package.time_limit_ms,
            "memory_limit_mb": package.memory_limit_mb,
            "tests": [
                {
                    "index": test.index,
                    "group": test.group,
                    "points": test.points,
                    "is_sample": test.is_sample,
                }
                for test in package.tests
            ],
        }

        buffer = BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(_MANIFEST, json.dumps(manifest, indent=2, ensure_ascii=False))
            archive.writestr(_CHECKER, package.checker)
            for test in package.tests:
                archive.writestr(f"tests/{test.index:02d}.in", test.input_data)
                archive.writestr(f"tests/{test.index:02d}.ans", test.answer_data)
            for name, data in package.files.items():
                archive.writestr(f"files/{name}", data)
        return buffer.getvalue()

    def materialize(self, archive: bytes) -> Package:
        try:
            with zipfile.ZipFile(BytesIO(archive)) as zip_file:
                names = set(zip_file.namelist())
                if _MANIFEST not in names:
                    raise PackageError(f"{_MANIFEST} is missing")
                manifest = json.loads(zip_file.read(_MANIFEST))

                tests = []
                for entry in manifest["tests"]:
                    index = entry["index"]
                    tests.append(
                        PackageTest(
                            index=index,
                            input_data=zip_file.read(f"tests/{index:02d}.in"),
                            answer_data=zip_file.read(f"tests/{index:02d}.ans"),
                            group=entry.get("group"),
                            points=entry.get("points", 0.0),
                            is_sample=entry.get("is_sample", False),
                        )
                    )

                files = {
                    name[len("files/"):]: zip_file.read(name)
                    for name in names
                    if name.startswith("files/") and not name.endswith("/")
                }

                return Package(
                    name=manifest["name"],
                    tests=tests,
                    checker=zip_file.read(_CHECKER) if _CHECKER in names else b"",
                    time_limit_ms=manifest.get("time_limit_ms", 1000),
                    memory_limit_mb=manifest.get("memory_limit_mb", 256),
                    files=files,
                )
        except zipfile.BadZipFile as exc:
            raise PackageError("not a zip archive") from exc
        except KeyError as exc:
            raise PackageError(f"archive is incomplete: {exc}") from exc
