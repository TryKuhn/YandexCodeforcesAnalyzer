"""Publishing to NlogN: ejudge export + statement + the NlogN problem (push) or the job result (pull)."""
import httpx
import pytest

import api.user.integrations.nlogn as nlogn
import api.user.nlogn.publish as publish
from api.crypt.secrets import encrypt
from models.user.integrations import NlognAccount, NlognPublication
from settings import settings
from tests.unit.ejudge.helpers import SERVE_CFG, FakeHost, package_zip
from tests.unit.integrations.test_nlogn import FakeNlogn
from tests.unit.nlogn.fixtures import HTML_STATEMENTS

CONTEST = "/home/judges/000042"
TESTS = [{"sample": True}, {}, {}]


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setattr(settings, "EJUDGE_SSH_HOST", "ejudge.local")
    monkeypatch.setattr(settings, "EJUDGE_JUDGES_DIR", "/home/judges")
    monkeypatch.setattr(settings, "EJUDGE_URL", "")
    monkeypatch.setattr(settings, "EJUDGE_GVALUER_PATH", "")
    monkeypatch.setattr(settings, "PUBLIC_URL", "https://tf.example")


@pytest.fixture
def polygon(polygon_api):
    data = package_zip(TESTS, statements=HTML_STATEMENTS)
    polygon_api.respond("problem.packages", [{"id": 4, "state": "READY"}, {"id": 5, "state": "FAILED"}])
    polygon_api.respond("problem.package", lambda params: data)
    return polygon_api


@pytest.fixture
def fake_nlogn(monkeypatch):
    fake = FakeNlogn()
    monkeypatch.setattr(nlogn, "_transport", httpx.MockTransport(fake))
    return fake


async def link_nlogn(db, user):
    db.add(NlognAccount(user_id=user.id, base_url="https://contest.example", token_enc=encrypt("nlogn-token-123"),
                        username="egor", full_name="Egor"))
    await db.commit()


def host() -> FakeHost:
    return FakeHost({f"{CONTEST}/conf/serve.cfg": SERVE_CFG.encode()})


async def test_push_exports_and_creates_the_nlogn_problem(polygon, fake_nlogn, db, user):
    await link_nlogn(db, user)
    request = publish.PublishRequest(polygon_id=555, ejudge_contest_id=42, short_name="C", nlogn_contest_id=15)
    result = await publish.run_publish(request, user.id, db, host_factory=host())

    assert result["ejudge_problem_id"] == 2 and result["short_name"] == "C"  # problem 1 exists in serve.cfg
    assert result["title"] == "Сумма" and result["package_id"] == 4 and result["revision"] == 7
    assert result["time_limit_ms"] == 1000 and result["memory_limit_mb"] == 256
    assert result["url"] == "https://tf.example/tasks/555"
    assert '<script type="math/tex">a</script>' in result["html_statement"]
    body = fake_nlogn.upserts[0]
    assert body["ejudgeContestId"] == 42 and body["ejudgeProblemId"] == 2 and body["addToContestId"] == 15
    assert body["source"] == {"system": "taskforge", "polygonId": 555, "packageId": 4, "revision": 7,
                              "url": "https://tf.example/tasks/555"}
    assert body["htmlStatement"] == result["html_statement"]
    assert result["nlogn"]["problem_id"] == 501 and result["nlogn"]["created"] is True
    assert result["nlogn"]["url"] == "https://contest.example/admin/problems/edit/501"
    assert result["nlogn"]["contest"]["symbolIndex"] == "C"

    row = await publish.latest_publication(db, user.id, 555)
    assert (row.ejudge_contest_id, row.ejudge_problem_id, row.short_name, row.nlogn_problem_id,
            row.nlogn_contest_id) == (42, 2, "C", 501, 15)

    # publishing again updates the same ejudge problem and the same publication row
    again = await publish.run_publish(publish.PublishRequest(polygon_id=555, ejudge_contest_id=42), user.id, db,
                                      host_factory=host())
    assert again["nlogn"]["created"] is False
    rows = (await db.execute(NlognPublication.__table__.select())).all()
    assert len(rows) == 1


async def test_pull_does_not_need_nlogn(polygon, fake_nlogn, db, user):
    result = await publish.run_publish(
        publish.PublishRequest(polygon_id=555, ejudge_contest_id=42, mode="pull"), user.id, db, host_factory=host())
    assert "nlogn" not in result and not fake_nlogn.requests
    assert result["ejudge_problem_id"] == 2 and result["html_statement"]
    assert (await publish.latest_publication(db, user.id, 555)).nlogn_problem_id is None


async def test_handler_reports_failures(polygon, fake_nlogn, db, user, monkeypatch):
    class Sessions:
        def __call__(self):
            return self

        async def __aenter__(self):
            return db

        async def __aexit__(self, *exc):
            return None

    handler = publish.make_handler(Sessions(), host_factory=host())

    async def progress(_):
        return None

    payload = {"user_id": user.id, "request": {"polygon_id": 555, "ejudge_contest_id": 42, "mode": "push"}}
    result = await handler(payload, progress)
    assert result["ok"] is False and "NlogN не привязан" in result["error"]

    await link_nlogn(db, user)
    fake_nlogn.upserts.append({})  # make the fake answer like an update
    monkeypatch.setattr(nlogn, "_transport", httpx.MockTransport(lambda r: httpx.Response(500, text="boom")))
    result = await handler(payload, progress)
    assert result["ok"] is False and "выгружена в ejudge" in result["error"] and "NlogN её не принял" in result["error"]
    # the ejudge part is remembered anyway
    assert (await publish.latest_publication(db, user.id, 555)).ejudge_problem_id == 2

    monkeypatch.setattr(nlogn, "_transport", httpx.MockTransport(fake_nlogn))
    result = await handler(payload, progress)
    assert result["ok"] is True and result["nlogn"]["problem_id"] == 501
