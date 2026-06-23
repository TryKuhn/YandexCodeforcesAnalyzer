"""Upload a parsed archive to Polygon.

Each problem is uploaded through a strict stage order, with every stage fully
completing before the next begins: create -> statement -> files (solutions +
checker/validator) -> tests -> groups/points -> commit -> build package. A
single aiohttp session with a semaphore is shared across the whole import
(faster than a session per request), and per-problem progress is written to the
job status for the frontend to poll.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

import aiohttp

from api.user.gpt.services.generation.checker_validator_gen import \
    generate_checker_validator
from api.user.polygon.archive.jobs import ImportJob, ProblemStatus
from api.user.polygon.archive.parser import (
    SOURCE_EXTENSIONS,
    TaskData,
    parse_archive,
    render_section,
)
from api.user.polygon.create_signature import create_signature
from settings import settings

logger = logging.getLogger(__name__)

TESTSET = "tests"
MAX_CONCURRENT_REQUESTS = 16
"""Polygon tolerates ~16 concurrent requests; 8 was noticeably slower on
archives with hundreds of tests."""
TESTLIB_PATH = Path(__file__).parent / "assets" / "testlib.h"


class PolygonError(Exception):
    """Raised when a Polygon API call fails after retries."""


def decode_text(data: bytes) -> str:
    """Decode bytes to str, trying utf-8 then cp1251, falling back to latin-1.

    Polygon requires every parameter (including file contents) to participate
    in the request signature as a string.
    """
    for enc in ("utf-8", "cp1251"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1")


class PolygonImportClient:
    """Polygon API client with a shared session, retries and a concurrency semaphore."""

    def __init__(self, api_key: str, api_secret: str):
        """Store credentials and create the request semaphore (session opens on enter)."""
        self.api_key = api_key
        self.api_secret = api_secret
        self.session: aiohttp.ClientSession | None = None
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def __aenter__(self) -> "PolygonImportClient":
        """Open the shared aiohttp session with a 5-minute total timeout."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=300)
        )
        return self

    async def __aexit__(self, *exc) -> None:
        """Close the shared aiohttp session."""
        if self.session:
            await self.session.close()

    async def call(self, method: str, **params):
        """Call a Polygon API method, signing the request and retrying on failure.

        ``None`` params are dropped and ``bytes`` values decoded to str. Up to
        three attempts handle transient failures: network/timeout errors, HTTP
        5xx, an expired timestamp (the time and signature are recomputed inside
        the semaphore so a queued request's timestamp stays within Polygon's
        5-minute window), and rate-limit responses, each with a backoff.
        Returns the ``result`` field on success, ``{}`` for non-JSON HTTP 200,
        and raises ``PolygonError`` otherwise.
        """
        text = {
            k: decode_text(v) if isinstance(v, bytes) else str(v)
            for k, v in params.items()
            if v is not None
        }
        last_err: Exception = PolygonError(f"{method}: неизвестная ошибка")
        for attempt in range(1, 4):
            try:
                async with self.semaphore:
                    full = {"apiKey": self.api_key, "time": str(int(time.time())), **text}
                    full["apiSig"] = create_signature(method, full, self.api_secret)
                    async with self.session.post(
                        f"{settings.POLYGON_HOST.rstrip('/')}/{method}", data=full
                    ) as resp:
                        body = await resp.text()
                        status = resp.status
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                last_err = PolygonError(f"{method}: {e!r}")
                await asyncio.sleep(2 * attempt)
                continue
            try:
                result = json.loads(body)
            except ValueError:
                if status >= 500:
                    last_err = PolygonError(f"{method}: HTTP {status}: {body[:200]}")
                    await asyncio.sleep(2 * attempt)
                    continue
                if status != 200:
                    raise PolygonError(f"{method}: HTTP {status}: {body[:300]}")
                return {}
            if result.get("status") == "OK":
                return result.get("result")
            comment = result.get("comment", body[:300])
            if "not within 5 minutes" in comment:
                last_err = PolygonError(f"{method}: {comment}")
                continue
            if any(s in comment.lower() for s in ("too many", "try again later", "limit exceeded")):
                last_err = PolygonError(f"{method}: {comment}")
                await asyncio.sleep(3 * attempt)
                continue
            raise PolygonError(f"{method}: {comment}")
        raise last_err


async def save_source_with_testlib_retry(
    client: PolygonImportClient,
    problem_id: int,
    name: str,
    code: str,
    status: ProblemStatus,
) -> None:
    """saveFile a source; if the problem lacks testlib.h, upload it and retry."""
    try:
        await client.call(
            "problem.saveFile",
            problemId=problem_id,
            type="source",
            name=name,
            file=code.encode(),
        )
    except PolygonError as e:
        if "testlib.h" not in str(e):
            raise
        await client.call(
            "problem.saveFile",
            problemId=problem_id,
            type="resource",
            name="testlib.h",
            file=TESTLIB_PATH.read_bytes(),
        )
        status.note("testlib.h добавлен в ресурсы задачи")
        await client.call(
            "problem.saveFile",
            problemId=problem_id,
            type="source",
            name=name,
            file=code.encode(),
        )


async def upload_task(
    client: PolygonImportClient,
    task: TaskData,
    status: ProblemStatus,
    *,
    generate_ai: bool,
    ai_model: str,
    build_pkg: bool,
) -> None:
    """Upload one parsed problem to Polygon through the strict stage order.

    Stages, each updating ``status.stage``: create/find the problem; set limits
    and save the statement and images; upload solutions plus an AI-generated
    checker/validator (the AI generation is kicked off early to overlap with
    the statement stage); upload tests; configure groups/points; commit; and
    optionally build the package. ``status`` is mutated throughout for progress
    polling.
    """
    st = task.statement

    status.stage = "create"
    existing = await client.call("problems.list", name=status.polygon_name)
    problem = next((p for p in existing or [] if p["name"] == status.polygon_name), None)
    if problem:
        problem_id = problem["id"]
        status.note(f"задача уже существует, id={problem_id}")
        await client.call("problem.updateWorkingCopy", problemId=problem_id)
    else:
        result = await client.call("problem.create", name=status.polygon_name)
        problem_id = result["id"] if isinstance(result, dict) else result
        status.note(f"создана задача id={problem_id}")
    status.polygon_id = problem_id

    ai_task: asyncio.Task | None = None
    if generate_ai and st is not None:
        ai_task = asyncio.create_task(generate_checker_validator(st, ai_model))

    status.stage = "statement"
    if st:
        await client.call(
            "problem.updateInfo",
            problemId=problem_id,
            inputFile=st.input_file,
            outputFile=st.output_file,
            timeLimit=st.time_limit_ms or 1000,
            memoryLimit=st.memory_limit_mb or 256,
        )
        await client.call(
            "problem.saveStatement",
            problemId=problem_id,
            lang="russian",
            encoding="utf-8",
            name=st.title or f"Задача {task.name}",
            legend=render_section(st.legend),
            input=render_section(st.input_format),
            output=render_section(st.output_format),
            scoring=render_section(st.scoring) or None,
            notes=render_section(st.notes) or None,
        )
        status.images_total = len(st.images)
        for img_name, img_data in st.images:
            await client.call(
                "problem.saveStatementResource",
                problemId=problem_id,
                name=img_name,
                file=img_data,
            )
        status.note(
            f"условие загружено (картинок: {len(st.images)}), "
            f"лимиты {st.time_limit_ms or 1000} мс / {st.memory_limit_mb or 256} МБ"
        )

    if task.groups:
        await client.call("problem.enablePoints", problemId=problem_id, enable="true")
        await client.call(
            "problem.enableGroups", problemId=problem_id, testset=TESTSET, enable="true"
        )

    status.stage = "files"
    uploadable = [
        s for s in task.solutions
        if ("." + s.name.rsplit(".", 1)[-1].lower() if "." in s.name else "")
        in SOURCE_EXTENSIONS
    ]
    skipped = [s.name for s in task.solutions if s not in uploadable]

    if uploadable and not any(s.tag == "MA" for s in uploadable):
        cand = next((s for s in uploadable if s.tag == "OK"), uploadable[0])
        cand.tag = "MA"
        status.note(f"{cand.name} назначено главным решением (MA)")
    status.solutions_total = len(uploadable) or 1

    async def upload_solution(sol) -> None:
        """Save one solution and bump the done counter."""
        await client.call(
            "problem.saveSolution",
            problemId=problem_id,
            name=sol.name,
            file=sol.data,
            tag=sol.tag,
            checkExisting="false",
        )
        status.solutions_done += 1

    if uploadable:
        results = await asyncio.gather(
            *(upload_solution(s) for s in uploadable), return_exceptions=True
        )
        errors = [r for r in results if isinstance(r, Exception)]
        if errors:
            raise PolygonError(f"решения: {errors[0]}")
    else:
        await client.call(
            "problem.saveSolution",
            problemId=problem_id,
            name="empty.py",
            file=b"",
            tag="MA",
            checkExisting="false",
        )
        status.solutions_done = 1
        status.note("исходников нет — добавлено пустое empty.py (MAIN) для задачи с открытыми тестами")
    if skipped:
        status.note(f"пропущено (не исходник): {', '.join(skipped)}")
    if task.dropped_tests:
        status.note(
            f"пропущены дубликаты тестов ({len(task.dropped_tests)}): "
            + ", ".join(task.dropped_tests)
        )

    if ai_task is not None:
        try:
            ai = await ai_task
        except Exception as e:
            status.note(f"ИИ чекер/валидатор: ошибка генерации — {e}")
            ai = None
        if ai:
            checker = ai.get("checker") or {}
            validator = ai.get("validator") or {}
            try:
                if checker.get("type") == "standard" and checker.get("name"):
                    await client.call(
                        "problem.setChecker", problemId=problem_id, checker=checker["name"]
                    )
                    status.checker = checker["name"]
                elif checker.get("code"):
                    await save_source_with_testlib_retry(
                        client, problem_id, "checker.cpp", checker["code"], status
                    )
                    await client.call(
                        "problem.setChecker", problemId=problem_id, checker="checker.cpp"
                    )
                    status.checker = "checker.cpp"
            except Exception as e:
                status.note(f"чекер: ошибка загрузки — {e}")
            try:
                if validator.get("code"):
                    await save_source_with_testlib_retry(
                        client, problem_id, "validator.cpp", validator["code"], status
                    )
                    await client.call(
                        "problem.setValidator", problemId=problem_id, validator="validator.cpp"
                    )
                    status.validator = "validator.cpp"
            except Exception as e:
                status.note(f"валидатор: ошибка загрузки — {e}")
            if ai.get("comment"):
                status.note(f"ИИ: {ai['comment']}")

    status.stage = "tests"
    status.tests_total = len(task.tests)

    async def upload_test(tst) -> None:
        """Save one test and bump the done counter."""
        await client.call(
            "problem.saveTest",
            problemId=problem_id,
            testset=TESTSET,
            testIndex=tst.index,
            testInput=tst.data,
            testGroup=tst.group,
            testPoints=tst.points,
            testUseInStatements="true" if tst.is_sample else None,
            checkExisting="false",
        )
        status.tests_done += 1

    results = await asyncio.gather(
        *(upload_test(t) for t in task.tests), return_exceptions=True
    )
    errors = [r for r in results if isinstance(r, Exception)]
    if errors:
        raise PolygonError(f"тесты: {errors[0]}")

    status.stage = "groups"
    groups_with_tests = {t.group for t in task.tests if t.group is not None}
    status.groups_total = len(task.groups)
    for g in task.groups:
        if g.name not in groups_with_tests:
            status.note(f"группа {g.name} осталась без тестов (дубликаты) — пропущена")
            continue
        await client.call(
            "problem.saveTestGroup",
            problemId=problem_id,
            testset=TESTSET,
            group=g.name,
            pointsPolicy="COMPLETE_GROUP",
            feedbackPolicy="ICPC",
            dependencies=",".join(g.dependencies) or None,
        )

    status.stage = "commit"
    await client.call(
        "problem.commitChanges",
        problemId=problem_id,
        minorChanges="true",
        message="Импорт из архива",
    )

    if build_pkg:
        status.stage = "build"
        await client.call(
            "problem.buildPackage", problemId=problem_id, full="true", verify="true"
        )
        status.note("пакет отправлен на сборку")

    status.stage = "done"


async def run_import(
    job: ImportJob,
    archive_bytes: bytes,
    *,
    api_key: str,
    api_secret: str,
    prefix: str,
    generate_ai: bool,
    ai_model: str,
    build_pkg: bool,
) -> None:
    """Background entry point: parse the archive and upload every problem.

    Parsing (CPU-bound) runs in an executor off the event loop; a parse failure
    marks the job ``error``. Otherwise a ``ProblemStatus`` is created per task,
    all problems are uploaded concurrently under one client, and per-problem
    failures are recorded without aborting the others. The job ends ``done``
    (with an aggregate error note if any problem failed) or ``error`` on an
    unexpected exception.
    """
    try:
        loop = asyncio.get_running_loop()
        tasks = await loop.run_in_executor(None, parse_archive, archive_bytes)
    except Exception as e:
        logger.exception("Archive parse failed")
        job.status = "error"
        job.error = f"Ошибка парсинга архива: {e}"
        return

    job.problems = [
        ProblemStatus(name=t.name, polygon_name=f"{prefix}{i}")
        for i, t in enumerate(tasks, 1)
    ]
    job.status = "running"

    try:
        async with PolygonImportClient(api_key, api_secret) as client:
            results = await asyncio.gather(
                *(
                    upload_task(
                        client,
                        task,
                        st,
                        generate_ai=generate_ai,
                        ai_model=ai_model,
                        build_pkg=build_pkg,
                    )
                    for task, st in zip(tasks, job.problems)
                ),
                return_exceptions=True,
            )
        for st, res in zip(job.problems, results):
            if isinstance(res, Exception):
                st.stage = "error"
                st.error = str(res)
                logger.warning(f"Import {job.id} problem {st.polygon_name}: {res}")
        job.status = "done"
        if any(p.stage == "error" for p in job.problems):
            job.error = "Часть задач загружена с ошибками"
    except Exception as e:
        logger.exception("Archive import failed")
        job.status = "error"
        job.error = str(e)
