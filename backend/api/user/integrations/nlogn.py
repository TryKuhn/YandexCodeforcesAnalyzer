"""``/api/integrations/nlogn``: the user's contest.nlogn.info (NlogN) admin account.

Linking signs in to NlogN with the admin's login and password once, keeps only
the long-lived NlogN token (encrypted, see ``api.crypt.secrets``) and checks that
the account is an NlogN admin. The token is used to publish problems there
(``api.user.nlogn``): NlogN's admin API authenticates with the ``X-Token`` header.
"""
from __future__ import annotations

import logging
from typing import Any

import httpx
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.crypt.secrets import SecretError, decrypt, encrypt
from api.user.integrations.base import integrations_router
from app.database import get_db
from models.user.integrations import NlognAccount

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://contest.nlogn.info"
TIMEOUT_SECONDS = 60

# set by tests
_transport: httpx.AsyncBaseTransport | None = None


class NlognError(Exception):
    """An NlogN call failed; ``status`` is the HTTP status (None when unreachable)."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


def _error_text(response: httpx.Response) -> str:
    try:
        data = response.json()
        err = data.get("error", data) if isinstance(data, dict) else data
        if isinstance(err, dict):
            return str(err.get("description") or err.get("message") or err)[:300]
        return str(err)[:300]
    except ValueError:
        return response.text[:300]


class NlognClient:
    """Thin client of the NlogN JSON API."""

    def __init__(self, base_url: str, token: str | None = None):
        self.base_url = base_url.rstrip("/")
        self.token = token

    async def _request(self, method: str, path: str, *, json: dict | None = None) -> Any:
        headers = {"X-Token": self.token} if self.token else {}
        try:
            async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS, transport=_transport) as client:
                response = await client.request(method, self.base_url + path, json=json, headers=headers)
        except httpx.HTTPError as e:
            raise NlognError(f"NlogN недоступен ({self.base_url}): {e!r}") from e
        if response.status_code in (401, 403):
            raise NlognError(
                f"NlogN отклонил запрос ({_error_text(response)}): привяжите NlogN в профиле заново "
                "под учётной записью администратора", response.status_code)
        if response.status_code == 404:
            raise NlognError(f"NlogN: {path} не найден ({_error_text(response)})", 404)
        if response.status_code >= 400:
            raise NlognError(f"NlogN: HTTP {response.status_code}: {_error_text(response)}", response.status_code)
        try:
            return response.json()
        except ValueError as e:
            raise NlognError(f"NlogN вернул не JSON на {path}") from e

    async def sign_in(self, login: str, password: str) -> str:
        data = await self._request("POST", "/api/user/authenticate/sign-in",
                                   json={"login": login, "password": password})
        token = data.get("token") if isinstance(data, dict) else None
        if not token:
            raise NlognError("NlogN не вернул токен входа")
        return str(token)

    async def whoami(self) -> dict:
        return await self._request("GET", "/api/admin/integration/whoami")

    async def contest(self, contest_id: int) -> dict:
        return await self._request("GET", f"/api/admin/contests/{contest_id}")

    async def upsert_ejudge_problem(self, payload: dict) -> dict:
        return await self._request("POST", "/api/admin/problems/upsert/ejudge", json=payload)


def problem_admin_url(base_url: str, problem_id: int) -> str:
    return f"{base_url.rstrip('/')}/admin/problems/edit/{problem_id}"


def contest_admin_url(base_url: str, contest_id: int) -> str:
    return f"{base_url.rstrip('/')}/admin/contests/edit/{contest_id}"


async def client_for(user_id: int, db: AsyncSession) -> NlognClient:
    """The client with the user's NlogN token; :class:`NlognError` when not linked."""
    account = await db.get(NlognAccount, user_id)
    if account is None:
        raise NlognError("NlogN не привязан: подключите его в профиле (раздел «Интеграции»)")
    try:
        token = decrypt(account.token_enc)
    except SecretError as e:
        raise NlognError(str(e)) from e
    return NlognClient(account.base_url, token)


class NlognLinkIn(BaseModel):
    base_url: str = Field(default=DEFAULT_BASE_URL, max_length=255)
    login: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=1000)

    @field_validator("base_url")
    @classmethod
    def _url(cls, value: str) -> str:
        value = (value or DEFAULT_BASE_URL).strip().rstrip("/")
        if not value.startswith(("https://", "http://")) or " " in value:
            raise ValueError("адрес NlogN должен начинаться с https://")
        return value


def _status(account: NlognAccount | None) -> dict:
    if account is None:
        return {"linked": False, "default_base_url": DEFAULT_BASE_URL}
    return {
        "linked": True,
        "default_base_url": DEFAULT_BASE_URL,
        "base_url": account.base_url,
        "username": account.username,
        "full_name": account.full_name,
        "nlogn_user_id": account.nlogn_user_id,
        "updated_at": account.updated_at.isoformat() if account.updated_at else None,
    }


def _http(e: NlognError) -> HTTPException:
    return HTTPException(status_code=502 if e.status is None or e.status >= 500 else 400, detail=str(e))


@integrations_router.get("/nlogn")
async def nlogn_status(user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    return _status(await db.get(NlognAccount, user_id))


@integrations_router.post("/nlogn")
async def nlogn_link(
    body: NlognLinkIn, user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    """Sign in to NlogN and keep the token; the password is used once and forgotten."""
    client = NlognClient(body.base_url)
    try:
        client.token = await client.sign_in(body.login.strip(), body.password)
        me = await client.whoami()
    except NlognError as e:
        if e.status == 401:
            raise HTTPException(status_code=400, detail="NlogN: неверный логин или пароль")
        raise _http(e)
    if not isinstance(me, dict) or not me.get("isAdmin"):
        raise HTTPException(status_code=400, detail="эта учётная запись NlogN не администратор: "
                                                    "публиковать задачи может только администратор")
    account = await db.get(NlognAccount, user_id)
    if account is None:
        account = NlognAccount(user_id=user_id)
        db.add(account)
    account.base_url = body.base_url
    account.token_enc = encrypt(client.token)
    account.nlogn_user_id = me.get("id")
    account.username = str(me.get("username") or body.login)[:255]
    account.full_name = str(me.get("fullName") or "")[:255]
    await db.commit()
    logger.info("NlogN linked: user_id=%s nlogn_user=%s", user_id, account.username)
    return _status(account)


@integrations_router.post("/nlogn/unlink")
async def nlogn_unlink(user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    account = await db.get(NlognAccount, user_id)
    if account is not None:
        await db.delete(account)
        await db.commit()
    return _status(None)


@integrations_router.get("/nlogn/contests/{contest_id}")
async def nlogn_contest(
    contest_id: int, user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    """A contest of NlogN (for the publication form: does it exist, what is it called)."""
    try:
        client = await client_for(user_id, db)
        contest = await client.contest(contest_id)
    except NlognError as e:
        # older NlogN versions answer 500 for a missing contest
        if e.status in (404, 500):
            raise HTTPException(status_code=404, detail=f"контест {contest_id} в NlogN не найден")
        raise _http(e)
    if not isinstance(contest, dict) or not contest.get("id"):
        raise HTTPException(status_code=404, detail=f"контест {contest_id} в NlogN не найден")
    problems = contest.get("problems") or []
    return {
        "id": contest["id"],
        "name": contest.get("name") or "",
        "problems_count": len(problems) if isinstance(problems, list) else 0,
        "url": contest_admin_url(client.base_url, int(contest["id"])),
    }
