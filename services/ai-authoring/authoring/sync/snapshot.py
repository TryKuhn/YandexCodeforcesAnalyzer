"""A snapshot of everything that defines a problem on Polygon.

File and solution sources are fetched incrementally: a file whose modification
time and length match the previous snapshot keeps its old content, so a sync
of an unchanged problem costs a dozen cheap list calls.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any

from authoring.polygon.client import PolygonClient, PolygonError

logger = logging.getLogger(__name__)

# resources nobody needs to read (and huge ones)
SKIP_CONTENT_NAMES = frozenset({"testlib.h", "olymp.sty", "problem.tex", "statements.ftl", "tutorial.tex"})
MAX_CONTENT_BYTES = 200_000
TEXT_EXTENSIONS = (
    ".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".py", ".java", ".kt", ".pas", ".dpr",
    ".txt", ".js", ".go", ".rs", ".cs", ".rb", ".sh", ".pl",
)
MAX_SAMPLES = 10
SAMPLE_PREVIEW_CHARS = 4000
MAX_PACKAGES = 5
_FETCH_CONCURRENCY = 6


class SnapshotError(Exception):
    """The problem cannot be read at all (no access, Polygon not linked, ...)."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _now() -> str:
    return datetime.now(UTC).replace(tzinfo=None).isoformat(timespec="seconds")


def _skip_reason(name: str, length: int | None) -> str | None:
    low = name.lower()
    if low in SKIP_CONTENT_NAMES:
        return "standard"
    if not low.endswith(TEXT_EXTENSIONS):
        return "binary"
    if length is not None and length > MAX_CONTENT_BYTES:
        return "too large"
    return None


async def _safe(errors: list[str], part: str, fn: Callable[[], Awaitable[Any]], default: Any) -> Any:
    try:
        return await fn()
    except PolygonError as e:
        errors.append(f"{part}: {e.message}")
        logger.info("snapshot %s failed: %s", part, e.message)
        return default


async def take_snapshot(client: PolygonClient, problem_id: int, previous: dict | None = None) -> dict:
    """Read the problem; ``previous`` provides contents of unchanged files."""
    previous = previous or {}
    errors: list[str] = []

    try:
        info = await client.info(problem_id)
    except PolygonError as e:
        raise SnapshotError(e.message) from e

    (
        statements, tags, files, checker, validator, interactor, script, tests, groups, packages,
    ) = await asyncio.gather(
        _safe(errors, "statements", lambda: client.statements(problem_id), {}),
        _safe(errors, "tags", lambda: client.tags(problem_id), []),
        _safe(errors, "files", lambda: client.files(problem_id), {}),
        _safe(errors, "checker", lambda: client.checker(problem_id), ""),
        _safe(errors, "validator", lambda: client.validator(problem_id), ""),
        _safe(errors, "interactor", lambda: client.interactor(problem_id), ""),
        _safe(errors, "script", lambda: client.script(problem_id), ""),
        _safe(errors, "tests", lambda: client.tests(problem_id), []),
        _safe(errors, "groups", lambda: client.groups(problem_id), []),
        _safe(errors, "packages", lambda: client.packages(problem_id), []),
    )

    semaphore = asyncio.Semaphore(_FETCH_CONCURRENCY)
    prev_files: dict = previous.get("files") or {}
    prev_solutions: dict = previous.get("solutions") or {}

    file_entries: dict[str, dict] = {}
    jobs: list[Awaitable[None]] = []

    for list_key, file_type in (("sourceFiles", "source"), ("resourceFiles", "resource"), ("auxFiles", "aux")):
        for f in (files or {}).get(list_key) or []:
            name = f.get("name") or ""
            key = f"{file_type}/{name}"
            entry = {
                "type": file_type,
                "name": name,
                "mtime": f.get("modificationTimeSeconds"),
                "length": f.get("length"),
                "sourceType": f.get("sourceType"),
                "content": None,
                "skipped": _skip_reason(name, f.get("length")),
            }
            file_entries[key] = entry
            old = prev_files.get(key)
            if entry["skipped"]:
                continue
            if old and old.get("mtime") == entry["mtime"] and old.get("length") == entry["length"] \
                    and old.get("content") is not None:
                entry["content"] = old["content"]
                continue

            async def fetch_file(entry: dict = entry) -> None:
                async with semaphore:
                    try:
                        entry["content"] = await client.view_file(problem_id, entry["type"], entry["name"])
                    except PolygonError as e:
                        errors.append(f"file {entry['name']}: {e.message}")

            jobs.append(fetch_file())

    solution_entries: dict[str, dict] = {}
    for s in (files or {}).get("solutions") or []:
        name = s.get("name") or ""
        entry = {
            "name": name,
            "tag": s.get("tag"),
            "mtime": s.get("modificationTimeSeconds"),
            "length": s.get("length"),
            "sourceType": s.get("sourceType"),
            "content": None,
            "skipped": _skip_reason(name, s.get("length")),
        }
        solution_entries[name] = entry
        old = prev_solutions.get(name)
        if entry["skipped"]:
            continue
        if old and old.get("mtime") == entry["mtime"] and old.get("length") == entry["length"] \
                and old.get("content") is not None:
            entry["content"] = old["content"]
            continue

        async def fetch_solution(entry: dict = entry) -> None:
            async with semaphore:
                try:
                    entry["content"] = await client.view_solution(problem_id, entry["name"])
                except PolygonError as e:
                    errors.append(f"solution {entry['name']}: {e.message}")

        jobs.append(fetch_solution())

    test_rows = [
        {
            "index": t.get("index"),
            "manual": bool(t.get("manual")),
            "group": t.get("group"),
            "points": t.get("points"),
            "useInStatements": bool(t.get("useInStatements")),
            "scriptLine": t.get("scriptLine"),
            "description": t.get("description"),
        }
        for t in tests or []
        if t.get("index") is not None
    ]
    test_rows.sort(key=lambda t: t["index"])

    samples: dict[str, str] = {}
    prev_samples: dict = previous.get("samples") or {}
    for t in [t for t in test_rows if t["useInStatements"]][:MAX_SAMPLES]:
        key = str(t["index"])

        async def fetch_sample(index: int = t["index"], key: str = key) -> None:
            async with semaphore:
                try:
                    text = await client.test_input(problem_id, index)
                    samples[key] = text[:SAMPLE_PREVIEW_CHARS]
                except PolygonError as e:
                    if key in prev_samples:
                        samples[key] = prev_samples[key]
                    errors.append(f"sample {index}: {e.message}")

        jobs.append(fetch_sample())

    if jobs:
        await asyncio.gather(*jobs)

    package_rows = sorted(
        (
            {
                "id": p.get("id"),
                "revision": p.get("revision"),
                "state": p.get("state"),
                "comment": p.get("comment") or "",
                "type": p.get("type"),
                "created": p.get("creationTimeSeconds"),
            }
            for p in packages or []
            if p.get("id") is not None
        ),
        key=lambda p: p["id"],
        reverse=True,
    )[:MAX_PACKAGES]

    return {
        "taken_at": _now(),
        "info": info or {},
        "statements": statements or {},
        "tags": list(tags or []),
        "files": file_entries,
        "solutions": solution_entries,
        "checker": checker or "",
        "validator": validator or "",
        "interactor": interactor or "",
        "script": script or "",
        "tests": test_rows,
        "samples": samples,
        "groups": [
            {
                "name": g.get("name"),
                "pointsPolicy": g.get("pointsPolicy"),
                "feedbackPolicy": g.get("feedbackPolicy"),
                "dependencies": list(g.get("dependencies") or []),
            }
            for g in groups or []
        ],
        "packages": package_rows,
        "errors": errors,
    }


def script_generators(script: str) -> list[str]:
    """Executable names the FreeMarker script calls (``gen 10 > $`` -> ``gen``)."""
    names: list[str] = []
    for raw in (script or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("<#") or line.startswith("</#") or ">" not in line:
            continue
        first = line.split()[0]
        if first.startswith(("<", "$")):
            continue
        if first not in names:
            names.append(first)
    return names


def file_role(snapshot: dict, entry: dict) -> str:
    """What a source file is for: checker / validator / interactor / generator / source."""
    name = entry.get("name") or ""
    stem = name.rsplit(".", 1)[0]
    if name == snapshot.get("checker"):
        return "checker"
    if name == snapshot.get("validator"):
        return "validator"
    if name == snapshot.get("interactor"):
        return "interactor"
    if entry.get("type") == "source" and stem in script_generators(snapshot.get("script") or ""):
        return "generator"
    return entry.get("type") or "source"
