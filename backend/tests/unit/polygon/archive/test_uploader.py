"""Unit tests for api.user.polygon.archive.uploader.

Every Polygon API call goes through ``PolygonImportClient.call``; in the
orchestration tests we replace the client with a fake that records calls and
returns scripted results, and we monkeypatch ``generate_checker_validator``.
The ``call`` retry/parse logic is tested directly against a fake aiohttp
session. No real network or aiohttp session is created.
"""
from __future__ import annotations

import asyncio

import pytest

import api.user.polygon.archive.uploader as U
from api.user.polygon.archive.uploader import (
    PolygonError,
    PolygonImportClient,
    decode_text,
    run_import,
    save_source_with_testlib_retry,
    upload_task,
)
from api.user.polygon.archive.jobs import ImportJob, ProblemStatus
from api.user.polygon.archive.parser import (
    Solution,
    Statement,
    TaskData,
    Test as PTest,  # aliased so pytest does not try to collect the dataclass
    TestGroup as PTestGroup,
)

pytestmark = pytest.mark.asyncio


async def _no_sleep(*_a, **_k):
    """Async no-op used to neutralise retry back-off delays."""
    return None


# ---------------------------------------------------------------------------
# decode_text
# ---------------------------------------------------------------------------


async def test_decode_text_utf8():
    assert decode_text("привет".encode("utf-8")) == "привет"


async def test_decode_text_cp1251_fallback():
    data = "тест".encode("cp1251")
    assert decode_text(data) == "тест"


async def test_decode_text_latin1_last_resort():
    # bytes invalid in utf-8 AND cp1251-undefined positions -> latin-1 never fails
    data = b"\x98\x9d"  # 0x98 is undefined in cp1251
    assert decode_text(data) == data.decode("latin-1")


# ---------------------------------------------------------------------------
# PolygonImportClient.call — fake aiohttp session
# ---------------------------------------------------------------------------


class _FakeResp:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    async def text(self):
        return self._body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False


class _FakeSession:
    """Returns scripted responses; raises if asked to send too many."""

    def __init__(self, responses, raises=None):
        self._responses = list(responses)
        self._raises = list(raises or [])
        self.calls = []

    def post(self, url, data=None):
        self.calls.append((url, data))
        if self._raises and self._raises[0] is not None:
            exc = self._raises.pop(0)
            self._responses.pop(0) if self._responses else None

            class _Raiser:
                async def __aenter__(_self):
                    raise exc

                async def __aexit__(_self, *e):
                    return False

            return _Raiser()
        if self._raises:
            self._raises.pop(0)
        return self._responses.pop(0)


def _client_with(session):
    c = PolygonImportClient("key", "secret")
    c.session = session
    return c


async def test_call_returns_result_on_ok(monkeypatch):
    monkeypatch.setattr(U, "create_signature", lambda *a, **k: "sig")
    sess = _FakeSession([_FakeResp(200, '{"status": "OK", "result": {"id": 7}}')])
    c = _client_with(sess)
    out = await c.call("problem.create", name="x")
    assert out == {"id": 7}
    # bytes params are decoded; None params dropped; apiKey/time/apiSig added
    _, data = sess.calls[0]
    assert data["apiKey"] == "key"
    assert "apiSig" in data and "time" in data
    assert data["name"] == "x"


async def test_call_raises_on_failed_status(monkeypatch):
    monkeypatch.setattr(U, "create_signature", lambda *a, **k: "sig")
    sess = _FakeSession([_FakeResp(200, '{"status": "FAILED", "comment": "bad thing"}')])
    c = _client_with(sess)
    with pytest.raises(PolygonError, match="bad thing"):
        await c.call("problem.x")


async def test_call_retries_on_rate_limit_then_succeeds(monkeypatch):
    monkeypatch.setattr(U, "create_signature", lambda *a, **k: "sig")
    monkeypatch.setattr(U.asyncio, "sleep", _no_sleep)
    sess = _FakeSession(
        [
            _FakeResp(200, '{"status": "FAILED", "comment": "Too many requests"}'),
            _FakeResp(200, '{"status": "OK", "result": "done"}'),
        ]
    )
    c = _client_with(sess)
    out = await c.call("problem.x")
    assert out == "done"
    assert len(sess.calls) == 2


async def test_call_retries_on_stale_time(monkeypatch):
    monkeypatch.setattr(U, "create_signature", lambda *a, **k: "sig")
    monkeypatch.setattr(U.asyncio, "sleep", _no_sleep)
    sess = _FakeSession(
        [
            _FakeResp(200, '{"status": "FAILED", "comment": "time is not within 5 minutes"}'),
            _FakeResp(200, '{"status": "OK", "result": 1}'),
        ]
    )
    c = _client_with(sess)
    assert await c.call("m") == 1
    assert len(sess.calls) == 2


async def test_call_non_json_2xx_returns_empty_dict(monkeypatch):
    monkeypatch.setattr(U, "create_signature", lambda *a, **k: "sig")
    sess = _FakeSession([_FakeResp(200, "not json")])
    c = _client_with(sess)
    assert await c.call("m") == {}


async def test_call_non_json_4xx_raises(monkeypatch):
    monkeypatch.setattr(U, "create_signature", lambda *a, **k: "sig")
    sess = _FakeSession([_FakeResp(403, "Forbidden")])
    c = _client_with(sess)
    with pytest.raises(PolygonError, match="HTTP 403"):
        await c.call("m")


async def test_call_5xx_retries(monkeypatch):
    monkeypatch.setattr(U, "create_signature", lambda *a, **k: "sig")
    monkeypatch.setattr(U.asyncio, "sleep", _no_sleep)
    sess = _FakeSession(
        [_FakeResp(500, "boom"), _FakeResp(200, '{"status":"OK","result":42}')]
    )
    c = _client_with(sess)
    assert await c.call("m") == 42


async def test_call_client_error_retried_then_exhausted(monkeypatch):
    import aiohttp

    monkeypatch.setattr(U, "create_signature", lambda *a, **k: "sig")
    monkeypatch.setattr(U.asyncio, "sleep", _no_sleep)
    err = aiohttp.ClientError("conn reset")
    sess = _FakeSession([None, None, None], raises=[err, err, err])
    c = _client_with(sess)
    with pytest.raises(PolygonError):
        await c.call("m")
    assert len(sess.calls) == 3  # three attempts


# ---------------------------------------------------------------------------
# fake client used by upload_task / save_source_with_testlib_retry
# ---------------------------------------------------------------------------


class FakeClient:
    """Records calls; ``scripts`` maps method -> callable(params)->result or raises."""

    def __init__(self, scripts=None):
        self.calls = []
        self.scripts = scripts or {}
        self.semaphore = asyncio.Semaphore(1)

    async def call(self, method, **params):
        self.calls.append((method, params))
        handler = self.scripts.get(method)
        if handler is not None:
            return handler(params)
        return {}

    def methods(self):
        return [m for m, _ in self.calls]


async def test_save_source_retry_uploads_testlib_then_retries(monkeypatch, tmp_path):
    testlib = tmp_path / "testlib.h"
    testlib.write_bytes(b"// testlib")
    monkeypatch.setattr(U, "TESTLIB_PATH", testlib)

    attempts = {"n": 0}

    def save_file(params):
        if params.get("type") == "source":
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise PolygonError("file testlib.h not found")
        return {}

    client = FakeClient({"problem.saveFile": save_file})
    status = ProblemStatus(name="A", polygon_name="x1")
    await save_source_with_testlib_retry(client, 1, "checker.cpp", "code", status)

    types = [p.get("type") for m, p in client.calls if m == "problem.saveFile"]
    assert types == ["source", "resource", "source"]  # fail, upload testlib, retry
    assert any("testlib.h" in n for n in status.log)


async def test_save_source_reraises_other_errors(monkeypatch):
    def save_file(params):
        raise PolygonError("compilation failed")

    client = FakeClient({"problem.saveFile": save_file})
    status = ProblemStatus(name="A", polygon_name="x1")
    with pytest.raises(PolygonError, match="compilation failed"):
        await save_source_with_testlib_retry(client, 1, "c.cpp", "code", status)


# ---------------------------------------------------------------------------
# upload_task orchestration
# ---------------------------------------------------------------------------


def _task_with_solution():
    return TaskData(
        name="A",
        solutions=[
            Solution(name="main.cpp", data=b"int main(){}", tag="MA"),
            Solution(name="notes.txt", data=b"x", tag=None),  # skipped (not source)
        ],
        tests=[
            PTest(index=1, name="01", data=b"in1\n", folder="samples", is_sample=True),
            PTest(index=2, name="02", data=b"in2\n", folder="grp1", group="1", points=50),
        ],
        groups=[PTestGroup(name="1", points=50, dependencies=[])],
        statement=Statement(
            letter="A",
            title="Сложение",
            time_limit_ms=2000,
            memory_limit_mb=256,
            legend=["text"],
        ),
    )


async def test_upload_task_full_happy_path():
    task = _task_with_solution()
    status = ProblemStatus(name="A", polygon_name="beloi1")
    client = FakeClient(
        {
            "problems.list": lambda p: [],  # not existing
            "problem.create": lambda p: {"id": 99},
        }
    )
    await upload_task(
        client, task, status, generate_ai=False, ai_model="m", build_pkg=True
    )

    methods = client.methods()
    assert "problem.create" in methods
    assert "problem.updateInfo" in methods
    assert "problem.saveStatement" in methods
    assert "problem.enableGroups" in methods
    assert "problem.saveSolution" in methods
    assert "problem.saveTest" in methods
    assert "problem.saveTestGroup" in methods
    assert "problem.commitChanges" in methods
    assert "problem.buildPackage" in methods
    assert status.stage == "done"
    assert status.polygon_id == 99
    assert status.solutions_done == 1  # only main.cpp uploadable
    assert status.tests_done == 2
    # notes.txt was skipped (not a source extension)
    assert any("notes.txt" in n for n in status.log)


async def test_upload_task_existing_problem_updates_working_copy():
    task = _task_with_solution()
    status = ProblemStatus(name="A", polygon_name="beloi1")
    client = FakeClient(
        {"problems.list": lambda p: [{"id": 5, "name": "beloi1"}]}
    )
    await upload_task(
        client, task, status, generate_ai=False, ai_model="m", build_pkg=False
    )
    assert ("problem.updateWorkingCopy", {"problemId": 5}) in client.calls
    assert status.polygon_id == 5
    assert "problem.buildPackage" not in client.methods()


async def test_upload_task_no_sources_creates_empty_main():
    task = TaskData(
        name="A",
        solutions=[],  # no sources at all
        tests=[PTest(index=1, name="01", data=b"in\n", folder="t")],
        groups=[],
        statement=None,
    )
    status = ProblemStatus(name="A", polygon_name="x1")
    client = FakeClient(
        {"problems.list": lambda p: [], "problem.create": lambda p: {"id": 1}}
    )
    await upload_task(
        client, task, status, generate_ai=False, ai_model="m", build_pkg=False
    )
    save_sol = [p for m, p in client.calls if m == "problem.saveSolution"]
    assert len(save_sol) == 1
    assert save_sol[0]["name"] == "empty.py"
    assert save_sol[0]["tag"] == "MA"
    assert status.solutions_done == 1


async def test_upload_task_promotes_main_when_none_tagged():
    task = TaskData(
        name="A",
        solutions=[Solution(name="sol.cpp", data=b"x", tag="OK")],
        tests=[],
        groups=[],
        statement=None,
    )
    status = ProblemStatus(name="A", polygon_name="x1")
    client = FakeClient(
        {"problems.list": lambda p: [], "problem.create": lambda p: {"id": 1}}
    )
    await upload_task(
        client, task, status, generate_ai=False, ai_model="m", build_pkg=False
    )
    assert task.solutions[0].tag == "MA"
    assert any("главным решением" in n for n in status.log)


async def test_upload_task_generates_ai_checker_and_validator(monkeypatch):
    task = _task_with_solution()
    status = ProblemStatus(name="A", polygon_name="x1")

    async def fake_gen(st, model):
        return {
            "checker": {"code": "// checker"},
            "validator": {"code": "// validator"},
            "comment": "looks good",
        }

    monkeypatch.setattr(U, "generate_checker_validator", fake_gen)
    client = FakeClient(
        {"problems.list": lambda p: [], "problem.create": lambda p: {"id": 1}}
    )
    await upload_task(
        client, task, status, generate_ai=True, ai_model="m", build_pkg=False
    )
    assert status.checker == "checker.cpp"
    assert status.validator == "validator.cpp"
    assert "problem.setChecker" in client.methods()
    assert "problem.setValidator" in client.methods()
    assert any("looks good" in n for n in status.log)


async def test_upload_task_standard_checker(monkeypatch):
    task = _task_with_solution()
    status = ProblemStatus(name="A", polygon_name="x1")

    async def fake_gen(st, model):
        return {"checker": {"type": "standard", "name": "wcmp"}, "validator": {}}

    monkeypatch.setattr(U, "generate_checker_validator", fake_gen)
    client = FakeClient(
        {"problems.list": lambda p: [], "problem.create": lambda p: {"id": 1}}
    )
    await upload_task(
        client, task, status, generate_ai=True, ai_model="m", build_pkg=False
    )
    assert status.checker == "wcmp"
    set_checker = [p for m, p in client.calls if m == "problem.setChecker"]
    assert set_checker[0]["checker"] == "wcmp"


async def test_upload_task_ai_generation_failure_is_non_fatal(monkeypatch):
    task = _task_with_solution()
    status = ProblemStatus(name="A", polygon_name="x1")

    async def fake_gen(st, model):
        raise RuntimeError("LLM down")

    monkeypatch.setattr(U, "generate_checker_validator", fake_gen)
    client = FakeClient(
        {"problems.list": lambda p: [], "problem.create": lambda p: {"id": 1}}
    )
    # Should not raise — AI errors are logged, import continues
    await upload_task(
        client, task, status, generate_ai=True, ai_model="m", build_pkg=False
    )
    assert status.stage == "done"
    assert any("ошибка генерации" in n for n in status.log)


async def test_upload_task_test_error_raises():
    task = _task_with_solution()
    status = ProblemStatus(name="A", polygon_name="x1")

    def save_test(params):
        raise PolygonError("invalid test")

    client = FakeClient(
        {
            "problems.list": lambda p: [],
            "problem.create": lambda p: {"id": 1},
            "problem.saveTest": save_test,
        }
    )
    with pytest.raises(PolygonError, match="тесты"):
        await upload_task(
            client, task, status, generate_ai=False, ai_model="m", build_pkg=False
        )


async def test_upload_task_solution_error_raises():
    task = _task_with_solution()
    status = ProblemStatus(name="A", polygon_name="x1")

    def save_sol(params):
        raise PolygonError("bad solution")

    client = FakeClient(
        {
            "problems.list": lambda p: [],
            "problem.create": lambda p: {"id": 1},
            "problem.saveSolution": save_sol,
        }
    )
    with pytest.raises(PolygonError, match="решения"):
        await upload_task(
            client, task, status, generate_ai=False, ai_model="m", build_pkg=False
        )


async def test_upload_task_skips_group_without_tests():
    # group "2" has no tests assigned -> skipped with a note
    task = TaskData(
        name="A",
        solutions=[Solution(name="m.cpp", data=b"x", tag="MA")],
        tests=[PTest(index=1, name="01", data=b"i\n", folder="g1", group="1")],
        groups=[PTestGroup(name="1", points=10), PTestGroup(name="2", points=20)],
        statement=None,
    )
    status = ProblemStatus(name="A", polygon_name="x1")
    client = FakeClient(
        {"problems.list": lambda p: [], "problem.create": lambda p: {"id": 1}}
    )
    await upload_task(
        client, task, status, generate_ai=False, ai_model="m", build_pkg=False
    )
    saved_groups = [p["group"] for m, p in client.calls if m == "problem.saveTestGroup"]
    assert saved_groups == ["1"]
    assert any("группа 2" in n for n in status.log)


# ---------------------------------------------------------------------------
# run_import
# ---------------------------------------------------------------------------


async def test_run_import_parse_failure_sets_error(monkeypatch):
    job = ImportJob(id="j1", user_id=1)

    def boom(_bytes):
        raise ValueError("corrupt zip")

    monkeypatch.setattr(U, "parse_archive", boom)
    await run_import(
        job,
        b"bytes",
        api_key="k",
        api_secret="s",
        prefix="pre",
        generate_ai=False,
        ai_model="m",
        build_pkg=False,
    )
    assert job.status == "error"
    assert "Ошибка парсинга" in job.error


async def test_run_import_success_builds_problem_statuses(monkeypatch):
    job = ImportJob(id="j1", user_id=1)
    tasks = [TaskData(name="A"), TaskData(name="B")]
    monkeypatch.setattr(U, "parse_archive", lambda _b: tasks)

    seen = []

    async def fake_upload(client, task, status, **kw):
        seen.append((task.name, status.polygon_name))
        status.stage = "done"

    monkeypatch.setattr(U, "upload_task", fake_upload)

    # Replace client context manager with a no-op fake
    class FakeCtx:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *e):
            return False

    monkeypatch.setattr(U, "PolygonImportClient", FakeCtx)

    await run_import(
        job,
        b"x",
        api_key="k",
        api_secret="s",
        prefix="beloi22-",
        generate_ai=False,
        ai_model="m",
        build_pkg=False,
    )
    assert job.status == "done"
    assert [p.polygon_name for p in job.problems] == ["beloi22-1", "beloi22-2"]
    assert seen == [("A", "beloi22-1"), ("B", "beloi22-2")]
    assert job.error is None


async def test_run_import_marks_partial_errors(monkeypatch):
    job = ImportJob(id="j1", user_id=1)
    monkeypatch.setattr(U, "parse_archive", lambda _b: [TaskData(name="A"), TaskData(name="B")])

    async def fake_upload(client, task, status, **kw):
        if task.name == "B":
            raise PolygonError("failed B")
        status.stage = "done"

    monkeypatch.setattr(U, "upload_task", fake_upload)

    class FakeCtx:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *e):
            return False

    monkeypatch.setattr(U, "PolygonImportClient", FakeCtx)

    await run_import(
        job,
        b"x",
        api_key="k",
        api_secret="s",
        prefix="p",
        generate_ai=False,
        ai_model="m",
        build_pkg=False,
    )
    assert job.status == "done"
    assert job.error == "Часть задач загружена с ошибками"
    b_status = next(p for p in job.problems if p.name == "B")
    assert b_status.stage == "error"
    assert b_status.error == "failed B"
