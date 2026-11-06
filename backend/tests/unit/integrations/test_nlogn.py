"""``/api/integrations/nlogn``: linking an NlogN admin account (only the token is kept)."""
import json

import httpx
import pytest
from fastapi import HTTPException

import api.user.integrations.nlogn as nlogn
from api.crypt.secrets import decrypt
from models.user.integrations import NlognAccount


class FakeNlogn:
    """contest.nlogn.info: sign-in, whoami, contests, upsert."""

    def __init__(self, *, admin: bool = True):
        self.admin = admin
        self.requests: list[httpx.Request] = []
        self.upserts: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if path == "/api/user/authenticate/sign-in":
            body = json.loads(request.content)
            if body["password"] != "right":
                return httpx.Response(401, json={"error": {"description": "Wrong login or password", "httpCode": 401}})
            return httpx.Response(200, json={"token": "nlogn-token-123"})
        if request.headers.get("x-token") != "nlogn-token-123":
            return httpx.Response(401, json={"error": {"description": "You are not logged in", "httpCode": 401}})
        if path == "/api/admin/integration/whoami":
            return httpx.Response(200, json={"id": 7, "username": "egor", "fullName": "Egor A", "isAdmin": self.admin})
        if path == "/api/admin/contests/15":
            return httpx.Response(200, json={"id": 15, "name": "Весна", "problems": [{"id": 1}]})
        if path.startswith("/api/admin/contests/"):
            return httpx.Response(500, json={"error": {"description": "Internal Server Error"}})
        if path == "/api/admin/problems/upsert/ejudge":
            body = json.loads(request.content)
            self.upserts.append(body)
            contest = {"id": body["addToContestId"], "name": "Весна", "symbolIndex": "C"} \
                if body.get("addToContestId") else None
            return httpx.Response(200, json={
                "problem": {"id": 501, "title": body["title"],
                            "foreignProblemIdentifier": f"{body['ejudgeContestId']}:{body['ejudgeProblemId']}"},
                "created": len(self.upserts) == 1, "contest": contest})
        return httpx.Response(404, json={"error": {"description": "not found"}})


@pytest.fixture
def fake_nlogn(monkeypatch):
    fake = FakeNlogn()
    monkeypatch.setattr(nlogn, "_transport", httpx.MockTransport(fake))
    return fake


async def test_link_keeps_only_the_token(fake_nlogn, db, user):
    status = await nlogn.nlogn_link(
        nlogn.NlognLinkIn(base_url="https://contest.example/", login="egor", password="right"),
        user_id=user.id, db=db)
    assert status["linked"] and status["username"] == "egor" and status["full_name"] == "Egor A"
    assert status["base_url"] == "https://contest.example"
    account = await db.get(NlognAccount, user.id)
    assert decrypt(account.token_enc) == "nlogn-token-123" and "right" not in account.token_enc
    assert fake_nlogn.requests[1].headers["x-token"] == "nlogn-token-123"

    contest = await nlogn.nlogn_contest(15, user_id=user.id, db=db)
    assert contest == {"id": 15, "name": "Весна", "problems_count": 1,
                       "url": "https://contest.example/admin/contests/edit/15"}
    with pytest.raises(HTTPException) as e:
        await nlogn.nlogn_contest(99, user_id=user.id, db=db)
    assert e.value.status_code == 404

    assert (await nlogn.nlogn_unlink(user_id=user.id, db=db))["linked"] is False
    assert await db.get(NlognAccount, user.id) is None


async def test_wrong_password_and_non_admin(fake_nlogn, db, user):
    with pytest.raises(HTTPException) as e:
        await nlogn.nlogn_link(nlogn.NlognLinkIn(login="egor", password="wrong"), user_id=user.id, db=db)
    assert e.value.status_code == 400 and "неверный логин" in e.value.detail
    fake_nlogn.admin = False
    with pytest.raises(HTTPException) as e:
        await nlogn.nlogn_link(nlogn.NlognLinkIn(login="egor", password="right"), user_id=user.id, db=db)
    assert "не администратор" in e.value.detail
    assert await db.get(NlognAccount, user.id) is None


async def test_unreachable_and_validation(monkeypatch, db, user):
    def down(request):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(nlogn, "_transport", httpx.MockTransport(down))
    with pytest.raises(HTTPException) as e:
        await nlogn.nlogn_link(nlogn.NlognLinkIn(login="egor", password="right"), user_id=user.id, db=db)
    assert e.value.status_code == 502 and "недоступен" in e.value.detail
    with pytest.raises(ValueError):
        nlogn.NlognLinkIn(base_url="javascript:alert(1)", login="a", password="b")
    with pytest.raises(HTTPException) as e:
        await nlogn.nlogn_contest(15, user_id=user.id, db=db)
    assert "не привязан" in e.value.detail
