"""The /api/ai proxy and the server-side client of the AI authoring service."""
import json

import httpx
import jwt
import pytest
from fastapi import Depends, FastAPI

import api.user.ai.client as ai_client
import api.user.ai.proxy as ai_proxy
from api.crypt import get_current_user
from api.user.ai import ai_proxy_router
from api.user.polygon.archive.parser import Statement
from settings import settings

pytestmark = pytest.mark.asyncio


def _token(user_id: int = 5) -> str:
    from datetime import datetime, timezone

    from api.crypt import create_token
    return create_token({"user_id": user_id}, datetime.now(timezone.utc), 5)


@pytest.fixture
def upstream(monkeypatch):
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["method"] = request.method
        seen["url"] = str(request.url)
        seen["headers"] = dict(request.headers)
        seen["body"] = request.content
        if request.url.path.endswith("/down"):
            raise httpx.ConnectError("refused")
        return httpx.Response(201, json={"echo": True}, headers={"x-internal": "1"})

    monkeypatch.setattr(ai_proxy, "_transport", httpx.MockTransport(handler))
    monkeypatch.setattr(settings, "AI_SERVICE_URL", "http://ai:8100/")
    return seen


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(ai_proxy_router, prefix="/api/ai", dependencies=[Depends(get_current_user)])
    return app


async def test_proxy_forwards_method_path_query_body_and_auth(app, upstream):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://be") as client:
        response = await client.post(
            "/api/ai/sessions/abc/messages?after=3&x=1",
            json={"text": "привет"},
            headers={"Authorization": f"Bearer {_token()}", "Cookie": "secret=1"},
        )
    assert response.status_code == 201 and response.json() == {"echo": True}
    assert "x-internal" not in response.headers
    assert upstream["method"] == "POST"
    assert upstream["url"] == "http://ai:8100/api/ai/sessions/abc/messages?after=3&x=1"
    assert upstream["headers"]["authorization"].startswith("Bearer ")
    assert "cookie" not in upstream["headers"]
    assert json.loads(upstream["body"]) == {"text": "привет"}


async def test_proxy_requires_token(app, upstream):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://be") as client:
        response = await client.get("/api/ai/models")
    assert response.status_code in (401, 403)
    assert upstream == {}


async def test_proxy_reports_unreachable_service(app, upstream):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://be") as client:
        response = await client.get("/api/ai/down", headers={"Authorization": f"Bearer {_token()}"})
    assert response.status_code == 503 and response.json()["detail"] == "Сервис ИИ недоступен"


def _statement() -> Statement:
    return Statement(letter="A", title="Сумма", time_limit_ms=1000, memory_limit_mb=256,
                     legend=["Даны $a$ и $b$."], input_format=["Два числа."], output_format=["Сумма."],
                     examples=[("1 2", "3")])


async def test_client_calls_assist_as_the_user(monkeypatch):
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"checker": {"type": "standard", "name": "std::ncmp.cpp"},
                                         "validator": {"code": "v"}, "comment": "c"})

    monkeypatch.setattr(ai_client, "_transport", httpx.MockTransport(handler))
    monkeypatch.setattr(settings, "AI_SERVICE_URL", "http://ai:8100")
    result = await ai_client.generate_checker_validator(_statement(), "anthropic/claude-opus-5.5", user_id=9)

    assert result["checker"]["name"] == "std::ncmp.cpp"
    assert seen["url"] == "http://ai:8100/api/ai/assist/checker-validator"
    payload = jwt.decode(seen["auth"].split()[1], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    assert payload["user_id"] == 9 and payload["svc"] == "backend"
    body = seen["body"]
    assert body["model"] == "anthropic/claude-opus-5.5"
    assert body["statement"]["name"] == "Сумма" and body["statement"]["examples"] == [["1 2", "3"]]
    assert "Даны $a$ и $b$." in body["statement"]["legend"]


@pytest.mark.parametrize("response", [
    httpx.Response(502, json={"detail": "Ошибка модели"}),
    httpx.Response(200, json={"comment": "no files"}),
])
async def test_client_errors(monkeypatch, response):
    monkeypatch.setattr(ai_client, "_transport", httpx.MockTransport(lambda r: response))
    with pytest.raises(ai_client.AIServiceError):
        await ai_client.generate_checker_validator(_statement(), "m", user_id=1)
