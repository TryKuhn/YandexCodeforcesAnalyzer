"""The export orchestration (fake SSH host and web), the job handler and the routes."""
import uuid

import httpx
import pytest
from fastapi import HTTPException

import api.user.ejudge.export as export
import api.user.ejudge.router as router
import api.user.ejudge.web as web
from api.user.ejudge.common import EjudgeError
from api.user.ejudge.web import EjudgeWeb
from api.user.polygon.client import PolygonAPIError
from models.jobs.job import Job
from settings import settings
from tests.unit.ejudge.helpers import SERVE_CFG, FakeHost, package_zip
from tests.unit.ejudge.test_convert import GROUPED_TESTS, GROUPS

CONTEST = "/home/judges/000042"


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(settings, "EJUDGE_SSH_HOST", "ejudge.local")
    monkeypatch.setattr(settings, "EJUDGE_JUDGES_DIR", "/home/judges")
    monkeypatch.setattr(settings, "EJUDGE_URL", "https://ej.local/cgi-bin")
    monkeypatch.setattr(settings, "EJUDGE_LOGIN", "admin")
    monkeypatch.setattr(settings, "EJUDGE_PASSWORD", "pw")
    monkeypatch.setattr(settings, "EJUDGE_GVALUER_PATH", "")


@pytest.fixture
def polygon(polygon_api):
    data = package_zip(GROUPED_TESTS, GROUPS)
    polygon_api.respond("problem.packages", [
        {"id": 3, "state": "READY"}, {"id": 5, "state": "FAILED"}, {"id": 4, "state": "READY"}])

    def download(params):
        if params["type"] == "linux":
            raise PolygonAPIError("no linux package")
        return data

    polygon_api.respond("problem.package", download)
    return polygon_api


class FakeWeb:
    calls: list = []

    def __init__(self, url, login, password):
        self.args = (url, login, password)

    async def reload_config(self, contest_id):
        FakeWeb.calls.append((self.args, contest_id))


def host_with_contest(**kwargs) -> FakeHost:
    return FakeHost({f"{CONTEST}/conf/serve.cfg": SERVE_CFG.encode()}, **kwargs)


async def test_export_uploads_compiles_and_reloads(polygon, db, user):
    host = host_with_contest()
    FakeWeb.calls = []
    request = export.ExportRequest(polygon_id=555, contest_id=42, short_name="C")
    progress = []

    async def track(p):
        progress.append(p)

    report = await export.run_export(request, user.id, db, host_factory=host, web_factory=FakeWeb, progress=track)

    assert report["package_id"] == 4 and report["reloaded"] is True
    assert polygon.last("problem.package").params["type"] == "windows"  # linux failed, fell back
    final = f"{CONTEST}/problems/a-plus-b"
    tree = host.tree(final)
    assert {"check", "check.cpp", "gvaluer", "gvaluer.cpp", "valuer.cfg", "problem.cfg", "testlib.h",
            "tests/001.dat", "tests/008.ans"} <= set(tree)
    assert not [k for k in host.files if ".upload-" in k]
    serve = host.files[f"{CONTEST}/conf/serve.cfg"].decode()
    assert 'short_name = "C"' in serve and 'extid = "polygon:555"' in serve
    assert "separate_user_score = 1" in serve
    assert [k for k in host.files if "/conf/serve.cfg.bak-" in k]
    assert FakeWeb.calls == [(("https://ej.local/cgi-bin", "admin", "pw"), 42)]
    assert progress[-1] == 100

    # a second export updates the same problem and keeps a backup of the old directory
    report2 = await export.run_export(request, user.id, db, host_factory=host, web_factory=FakeWeb)
    serve2 = host.files[f"{CONTEST}/conf/serve.cfg"].decode()
    assert serve2.count('extid = "polygon:555"') == 1
    assert any(".a-plus-b.bak-" in k for k in host.files)
    assert report2["problem_id"] == report["problem_id"]


async def test_preview_writes_nothing(polygon, db, user):
    host = host_with_contest()
    before = dict(host.files)
    report = await export.run_export(export.ExportRequest(polygon_id=555, contest_id=42), user.id, db,
                                     dry_run=True, host_factory=host)
    assert report["dry_run"] and "group 2 {" in report["valuer_cfg"]
    assert report["groups"][1] == {"name": "1", "tests": "3-6", "score": 30.0, "each_test": False,
                                   "requires": ["0"], "feedback": "brief"}
    assert host.files == before and host.commands == []


async def test_compile_failure_cleans_staging(polygon, db, user):
    host = host_with_contest(fail_compile="check.cpp")
    with pytest.raises(EjudgeError, match="компиляция check.cpp"):
        await export.run_export(export.ExportRequest(polygon_id=555, contest_id=42), user.id, db,
                                host_factory=host, web_factory=FakeWeb)
    assert not [k for k in host.files if "/problems/" in k]
    assert host.files[f"{CONTEST}/conf/serve.cfg"] == SERVE_CFG.encode()


async def test_existing_gvaluer_binary_is_copied(polygon, db, user, monkeypatch):
    monkeypatch.setattr(settings, "EJUDGE_GVALUER_PATH", "/opt/ejudge/gvaluer")
    host = host_with_contest()
    host.files["/opt/ejudge/gvaluer"] = b"ELF"
    await export.run_export(export.ExportRequest(polygon_id=555, contest_id=42), user.id, db,
                            host_factory=host, web_factory=FakeWeb)
    tree = host.tree(f"{CONTEST}/problems/a-plus-b")
    assert "gvaluer" in tree and "gvaluer.cpp" not in tree


async def test_reload_failure_is_a_warning(polygon, db, user):
    class BrokenWeb(FakeWeb):
        async def reload_config(self, contest_id):
            raise EjudgeError("ejudge: не удалось войти")

    report = await export.run_export(export.ExportRequest(polygon_id=555, contest_id=42), user.id, db,
                                     host_factory=host_with_contest(), web_factory=BrokenWeb)
    assert report["reloaded"] is False and any("не перезагружена" in w for w in report["warnings"])


async def test_package_selection_errors(polygon_api, db, user):
    polygon_api.respond("problem.packages", [{"id": 1, "state": "FAILED"}])
    with pytest.raises(EjudgeError, match="нет собранного пакета"):
        await export.fetch_package(555, None, user.id, db)
    with pytest.raises(EjudgeError, match="не найден"):
        await export.fetch_package(555, 1, user.id, db)


async def test_not_configured(monkeypatch, db, user):
    monkeypatch.setattr(settings, "EJUDGE_SSH_HOST", "")
    with pytest.raises(EjudgeError, match="не настроен"):
        await export.run_export(export.ExportRequest(polygon_id=1, contest_id=1), user.id, db)


async def test_job_handler_returns_failures(polygon_api, db, user):
    polygon_api.respond("problem.packages", [])

    class Factory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return db

        async def __aexit__(self, *exc):
            return None

    handler = export.make_handler(Factory(), host_factory=host_with_contest())

    async def progress(_):
        return None

    result = await handler({"request": {"polygon_id": 555, "contest_id": 42}, "user_id": user.id}, progress)
    assert result["ok"] is False and "нет собранного пакета" in result["error"]


async def test_serve_cfg_edited_during_export(polygon, db, user):
    serve = f"{CONTEST}/conf/serve.cfg"

    def harmless(host):  # someone changes the contest time meanwhile: kept, export goes on
        host.files[serve] = host.files[serve].replace(b"contest_time = 300", b"contest_time = 240")

    host = host_with_contest()
    host.after_read[1] = harmless
    await export.run_export(export.ExportRequest(polygon_id=555, contest_id=42), user.id, db,
                            host_factory=host, web_factory=FakeWeb)
    text = host.files[serve].decode()
    assert "contest_time = 240" in text and 'extid = "polygon:555"' in text
    assert not [k for k in host.files if ".tmp-" in k]

    def conflicting(host):  # problem id 2 got taken by somebody else
        host.files[serve] += b'\n[problem]\nid = 2\nshort_name = "B"\ninternal_name = "zzz"\n'

    host = host_with_contest()
    host.after_read[1] = conflicting
    with pytest.raises(EjudgeError, match="изменился во время экспорта"):
        await export.run_export(export.ExportRequest(polygon_id=555, contest_id=42), user.id, db,
                                host_factory=host, web_factory=FakeWeb)
    assert not [k for k in host.files if "/problems/" in k]
    assert b"zzz" in host.files[serve] and b"polygon:555" not in host.files[serve]


async def test_failed_serve_cfg_write_restores_problem_dir(polygon, db, user):
    host = host_with_contest()
    await export.run_export(export.ExportRequest(polygon_id=555, contest_id=42), user.id, db,
                            host_factory=host, web_factory=FakeWeb)
    final = f"{CONTEST}/problems/a-plus-b"
    host.files[f"{final}/marker"] = b"first export"
    before_cfg = host.files[f"{CONTEST}/conf/serve.cfg"]
    host.fail_rename = True
    with pytest.raises(EjudgeError, match="переименовать"):
        await export.run_export(export.ExportRequest(polygon_id=555, contest_id=42), user.id, db,
                                host_factory=host, web_factory=FakeWeb)
    assert host.files[f"{final}/marker"] == b"first export"  # the old directory is back
    assert host.files[f"{CONTEST}/conf/serve.cfg"] == before_cfg
    # the serve.cfg backup is taken before the directory swap
    backup_at = next(i for i, c in enumerate(host.commands) if "serve.cfg.bak-" in c and c.startswith("cp"))
    swap_at = max(i for i, c in enumerate(host.commands) if c.startswith("if [ -e"))
    assert backup_at < swap_at


async def test_allowed_contests(polygon, db, user, monkeypatch):
    monkeypatch.setattr(settings, "EJUDGE_ALLOWED_CONTESTS", "7, 8")
    assert settings.ejudge_allowed_contests == {7, 8}
    with pytest.raises(EjudgeError, match="EJUDGE_ALLOWED_CONTESTS"):
        await export.run_export(export.ExportRequest(polygon_id=555, contest_id=42), user.id, db,
                                host_factory=host_with_contest())
    with pytest.raises(EjudgeError, match="EJUDGE_ALLOWED_CONTESTS"):
        await export.contest_info(42, host_factory=host_with_contest())


async def test_job_handler_reports_unexpected_errors(db, user, monkeypatch):
    async def boom(*args, **kwargs):
        raise RuntimeError("socket closed")

    monkeypatch.setattr(export, "run_export", boom)

    class Factory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return db

        async def __aexit__(self, *exc):
            return None

    async def progress(_):
        return None

    result = await export.make_handler(Factory())({"request": {"polygon_id": 1, "contest_id": 2}, "user_id": 1},
                                                  progress)
    assert result["ok"] is False and "socket closed" in result["error"]


# --------------------------------------------------------------------------- web
async def test_web_reload_flow(monkeypatch):
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        raw = request.content.decode()
        body = dict(x.split("=", 1) for x in raw.split("&")) if raw else {}
        seen.append((request.url.path, body))
        if request.url.path.endswith("serve-control") and "login" in body:
            return httpx.Response(302, headers={"Location": "https://ej.local/cgi-bin/serve-control?SID=abc123"})
        if body.get("action") == "3":
            return httpx.Response(302, headers={"Location": "https://ej.local/cgi-bin/new-master?SID=m77&x=1"})
        return httpx.Response(200, text="<html>ok</html>")

    monkeypatch.setattr(web, "_transport", httpx.MockTransport(handler))
    await EjudgeWeb("https://ej.local/cgi-bin/", "admin", "pw").reload_config(42)
    posts = [(p, b) for p, b in seen if b]
    assert posts[0] == ("/cgi-bin/serve-control", {"login": "admin", "password": "pw"})
    assert posts[1] == ("/cgi-bin/new-master", {"contest_id": "42", "SID": "abc123", "action": "3"})
    assert posts[2] == ("/cgi-bin/new-master", {"SID": "m77", "action": "62"})


async def test_web_bad_login(monkeypatch):
    monkeypatch.setattr(web, "_transport", httpx.MockTransport(lambda r: httpx.Response(200, text="login")))
    with pytest.raises(EjudgeError, match="логин"):
        await EjudgeWeb("https://ej.local/cgi-bin", "admin", "bad").reload_config(1)


# --------------------------------------------------------------------------- routes
async def test_routes_status_export_and_job(db, user, monkeypatch):
    assert (await router.route_status())["configured"] is True

    monkeypatch.setattr(router, "_enqueue", None)
    body = router.ExportIn(polygon_id=555, contest_id=42)
    with pytest.raises(HTTPException) as e:
        await router.route_export(body, user_id=user.id, db=db)
    assert e.value.status_code == 503

    async def fake_enqueue(db_, job_type, payload, user_id=None):
        job = Job(id=uuid.uuid4(), type=job_type, payload=payload, user_id=user_id)
        db_.add(job)
        await db_.commit()
        return job

    monkeypatch.setattr(router, "_enqueue", fake_enqueue)
    queued = await router.route_export(body, user_id=user.id, db=db)
    status = await router.route_export_status(uuid.UUID(queued["job_id"]), user_id=user.id, db=db)
    assert status["status"] == "queued" and status["progress"] == 0
    with pytest.raises(HTTPException) as e:
        await router.route_export_status(uuid.UUID(queued["job_id"]), user_id=user.id + 1, db=db)
    assert e.value.status_code == 404


async def test_route_contest_reports_errors(monkeypatch):
    async def broken(contest_id):
        raise EjudgeError("не удалось подключиться к ejudge по SSH: refused")

    monkeypatch.setattr(export, "contest_info", broken)
    with pytest.raises(HTTPException) as e:
        await router.route_contest(42, user_id=1)
    assert e.value.status_code == 400 and "SSH" in e.value.detail


async def test_contest_info_reads_serve_cfg():
    info = await export.contest_info(42, host_factory=host_with_contest())
    assert info["score_system"] == "olympiad" and info["advanced_layout"]
    assert info["problems"] == [{"id": "1", "short_name": "A", "long_name": "Old problem", "internal_name": "old",
                                 "extid": None}]


def test_export_in_validation():
    with pytest.raises(ValueError):
        router.ExportIn(polygon_id=1, contest_id=1, internal_name="../etc")
    with pytest.raises(ValueError):
        router.ExportIn(polygon_id=1, contest_id=1, short_name="a b")
