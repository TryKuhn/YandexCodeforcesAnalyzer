"""``/api/public/v1`` (personal access tokens only) and ``/api/nlogn`` (jury JWT)."""
import uuid
from datetime import datetime, timezone

import httpx
import pytest
from fastapi import Depends, FastAPI

import api.user.nlogn.router as nlogn_routes
from api.crypt import create_token, get_current_user
from api.user.integrations import integrations_router
from api.user.nlogn import nlogn_router, public_router
from app.database import get_db
from models.jobs.job import Job, JobStatus
from models.task.problem import PolygonProblem
from api.crypt.secrets import encrypt
from models.user.integrations import ApiToken, NlognAccount, NlognPublication
from settings import settings


@pytest.fixture
def app(db, monkeypatch):
    monkeypatch.setattr(settings, "EJUDGE_SSH_HOST", "ejudge.local")
    monkeypatch.setattr(settings, "EJUDGE_ALLOWED_CONTESTS", "")
    app = FastAPI()
    app.include_router(integrations_router, prefix="/api/integrations", dependencies=[Depends(get_current_user)])
    app.include_router(nlogn_router, prefix="/api/nlogn", dependencies=[Depends(get_current_user)])
    app.include_router(public_router, prefix="/api/public/v1")

    async def override_db():
        yield db

    app.dependency_overrides[get_db] = override_db

    async def enqueue(session, job_type, payload, user_id=None):
        job = Job(type=job_type, payload=payload, user_id=user_id)
        session.add(job)
        await session.commit()
        await session.refresh(job)
        return job

    monkeypatch.setattr(nlogn_routes, "_enqueue", enqueue)
    return app


def jwt_for(user_id: int) -> dict:
    return {"Authorization": f"Bearer {create_token({'user_id': user_id}, datetime.now(timezone.utc), 5)}"}


async def client(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://be")


async def test_tokens_and_their_isolation(app, db, user):
    async with await client(app) as c:
        created = (await c.post("/api/integrations/tokens", json={"name": "NlogN"}, headers=jwt_for(user.id))).json()
        token = created["token"]
        assert token.startswith("tfp_") and created["hint"].startswith("tfp_") and token not in created["hint"]
        pat = {"Authorization": f"Bearer {token}"}

        me = await c.get("/api/public/v1/me", headers=pat)
        assert me.status_code == 200 and me.json() == {"id": user.id, "login": "tester"}
        # a PAT is not a JWT, a JWT is not a PAT
        assert (await c.get("/api/integrations/tokens", headers=pat)).status_code == 401
        assert (await c.get("/api/nlogn/status", headers=pat)).status_code == 401
        assert (await c.get("/api/public/v1/me", headers=jwt_for(user.id))).status_code == 401
        assert (await c.get("/api/public/v1/me")).status_code == 401
        assert (await c.get("/api/public/v1/me", headers={"Authorization": "Bearer tfp_forged"})).status_code == 401

        # only the hash is stored; the list never shows the token
        row = (await db.execute(ApiToken.__table__.select())).first()
        assert token not in row.token_hash and len(row.token_hash) == 64
        listed = (await c.get("/api/integrations/tokens", headers=jwt_for(user.id))).json()["tokens"]
        assert [t["name"] for t in listed] == ["NlogN"] and "token" not in listed[0]
        assert listed[0]["last_used_at"] is not None

        revoked = await c.delete(f"/api/integrations/tokens/{created['id']}", headers=jwt_for(user.id))
        assert revoked.json() == {"tokens": []}
        assert (await c.get("/api/public/v1/me", headers=pat)).status_code == 401


async def test_public_problems_publish_and_job(app, db, user, polygon_api):
    polygon_api.respond("problems.list", [{"id": 555, "name": "a-plus-b", "owner": "tester", "revision": 7,
                                           "latestPackage": 7}, {"id": 556, "name": "other", "owner": "tester"}])
    db.add(NlognPublication(user_id=user.id, polygon_id=555, ejudge_contest_id=42, ejudge_problem_id=2,
                            short_name="C"))
    await db.commit()
    async with await client(app) as c:
        token = (await c.post("/api/integrations/tokens", json={"name": "x"}, headers=jwt_for(user.id))).json()["token"]
        pat = {"Authorization": f"Bearer {token}"}

        listing = (await c.get("/api/public/v1/problems?search=plus", headers=pat)).json()
        assert listing["total"] == 1
        assert listing["items"] == [{"polygon_id": 555, "name": "a-plus-b", "statement_name": None, "revision": 7,
                                     "latest_package": 7,
                                     "ejudge": {"contest_id": 42, "problem_id": 2, "short_name": "C"}}]
        assert (await db.execute(PolygonProblem.__table__.select())).all()

        queued = await c.post("/api/public/v1/problems/555/publish", json={"ejudge_contest_id": 42}, headers=pat)
        job_id = queued.json()["job_id"]
        job = await db.get(Job, uuid.UUID(job_id))
        assert job.type == "nlogn.publish" and job.payload["request"]["mode"] == "pull"
        assert job.payload["request"]["polygon_id"] == 555

        assert (await c.get(f"/api/public/v1/jobs/{job_id}", headers=pat)).json()["status"] == "queued"
        job.status = JobStatus.DONE.value
        job.result = {"ok": True, "ejudge_contest_id": 42, "ejudge_problem_id": 2, "short_name": "C", "title": "T",
                      "html_statement": "<div></div>", "text_statement": "", "time_limit_ms": 1000,
                      "memory_limit_mb": 256, "polygon_id": 555, "package_id": 4, "revision": 7,
                      "url": "u", "warnings": [], "statement_source": "html"}
        await db.commit()
        done = (await c.get(f"/api/public/v1/jobs/{job_id}", headers=pat)).json()
        assert done["status"] == "done" and done["result"]["ejudge_problem_id"] == 2
        assert "statement_source" not in done["result"]

        job.result = {"ok": False, "error": "нет пакета"}
        await db.commit()
        failed = (await c.get(f"/api/public/v1/jobs/{job_id}", headers=pat)).json()
        assert failed == {"job_id": job_id, "status": "failed", "progress": 0, "error": "нет пакета"}

        # someone else's token does not see the job
        from models.user.user import User
        other = User(login="other", password="x", email="o@example.com", role_id=user.role_id)
        db.add(other)
        await db.commit()
        other_token = (await c.post("/api/integrations/tokens", json={"name": "x"},
                                    headers=jwt_for(other.id))).json()["token"]
        resp = await c.get(f"/api/public/v1/jobs/{job_id}", headers={"Authorization": f"Bearer {other_token}"})
        assert resp.status_code == 404


async def test_jury_publish_requires_links(app, db, user):
    async with await client(app) as c:
        resp = await c.post("/api/nlogn/publish", json={"polygon_id": 555, "ejudge_contest_id": 42},
                            headers=jwt_for(user.id))
        assert resp.status_code == 400 and "NlogN не привязан" in resp.json()["detail"]
        status = (await c.get("/api/nlogn/status?polygon_id=555", headers=jwt_for(user.id))).json()
        assert status["nlogn"]["linked"] is False and status["ejudge"]["configured"] is True
        assert status["publication"] is None

        db.add(NlognAccount(user_id=user.id, base_url="https://contest.example", token_enc=encrypt("t")))
        await db.commit()
        resp = await c.post("/api/nlogn/publish", json={"polygon_id": 555, "ejudge_contest_id": 42,
                                                        "nlogn_contest_id": 15, "title": "Сумма"},
                            headers=jwt_for(user.id))
        job = await db.get(Job, uuid.UUID(resp.json()["job_id"]))
        assert job.payload["request"] == {"polygon_id": 555, "ejudge_contest_id": 42, "short_name": None,
                                          "package_id": None, "title": "Сумма", "nlogn_contest_id": 15,
                                          "mode": "push"}
        status = (await c.get(f"/api/nlogn/publish/{job.id}", headers=jwt_for(user.id))).json()
        assert status["status"] == "queued"
