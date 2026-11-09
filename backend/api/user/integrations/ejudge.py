"""``/api/integrations/ejudge``: the user's own ejudge host for the Polygon -> ejudge export.

SSH by private key or by password; the host key is pinned (SHA256 fingerprint or
known_hosts line) unless the user explicitly turns the check off. Secrets are
stored encrypted and never returned: a status shows only non-secret fields.
Re-saving the form with empty secret fields keeps the stored secrets.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from typing import Literal

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.crypt.secrets import SecretError, decrypt_optional, encrypt, encrypt_optional
from api.user.ejudge.common import EjudgeError
from api.user.ejudge.config import EjudgeConfig, parse_contests, server_config
from api.user.ejudge.remote import EjudgeHost, SSHHost, host_key_fingerprint, normalize_fingerprint, q
from api.user.ejudge.web import EjudgeWeb
from api.user.integrations.base import integrations_router
from app.database import get_db
from models.user.integrations import EjudgeAccount
from settings import settings

_HOST_RE = re.compile(r"^[A-Za-z0-9.\-]+$|^\[?[0-9A-Fa-f:.]+\]?$")

# replaced in tests
host_factory: Callable[[EjudgeConfig], EjudgeHost] = SSHHost
web_factory: Callable[[str, str, str], EjudgeWeb] = EjudgeWeb
fingerprint_probe = host_key_fingerprint


class EjudgeLinkIn(BaseModel):
    ssh_host: str = Field(min_length=1, max_length=255)
    ssh_port: int = Field(default=22, ge=1, le=65535)
    ssh_user: str = Field(default="ejudge", min_length=1, max_length=64, pattern=r"^[A-Za-z0-9._-]+$")
    auth_method: Literal["key", "password"]
    # empty secret fields keep what is stored
    ssh_key: str | None = Field(default=None, max_length=20000)
    ssh_key_passphrase: str | None = Field(default=None, max_length=1000)
    ssh_password: str | None = Field(default=None, max_length=1000)
    host_key: str | None = Field(default=None, max_length=10000)
    insecure_host_key: bool = False
    judges_dir: str = Field(default="/home/judges", min_length=1, max_length=255, pattern=r"^/[^\x00\n]*$")
    web_url: str | None = Field(default=None, max_length=255)
    web_login: str | None = Field(default=None, max_length=100)
    web_password: str | None = Field(default=None, max_length=1000)
    allowed_contests: str = Field(default="", max_length=500, pattern=r"^[0-9,;\s]*$")
    verify: bool = True

    @field_validator("ssh_host")
    @classmethod
    def _host(cls, value: str) -> str:
        value = value.strip()
        if not _HOST_RE.match(value):
            raise ValueError("недопустимое имя хоста")
        return value

    @field_validator("web_url")
    @classmethod
    def _url(cls, value: str | None) -> str | None:
        value = (value or "").strip().rstrip("/")
        if value and not re.match(r"^https?://[^\s]+$", value):
            raise ValueError("адрес веб-интерфейса должен начинаться с http:// или https://")
        return value or None


def _config_from(body: EjudgeLinkIn, existing: EjudgeAccount | None) -> EjudgeConfig:
    """What the form describes, with stored secrets filling the empty secret fields."""
    same_method = existing is not None and existing.auth_method == body.auth_method
    try:
        stored_secret = decrypt_optional(existing.ssh_secret_enc) if same_method and existing else ""
        stored_passphrase = decrypt_optional(existing.ssh_key_passphrase_enc) if same_method and existing else ""
        stored_web = decrypt_optional(existing.web_password_enc) if existing else ""
    except SecretError:
        stored_secret = stored_passphrase = stored_web = ""
    if body.auth_method == "key":
        key = (body.ssh_key or "").strip() or stored_secret
        if not key:
            raise HTTPException(status_code=400, detail="укажите приватный ключ SSH")
        passphrase = body.ssh_key_passphrase or ("" if body.ssh_key else stored_passphrase)
        password = ""
    else:
        password = body.ssh_password or stored_secret
        if not password:
            raise HTTPException(status_code=400, detail="укажите пароль SSH")
        key = passphrase = ""
    return EjudgeConfig(
        source="user",
        ssh_host=body.ssh_host,
        ssh_port=body.ssh_port,
        ssh_user=body.ssh_user,
        ssh_key=key + ("\n" if key and not key.endswith("\n") else ""),
        ssh_key_passphrase=passphrase,
        ssh_password=password,
        host_key=normalize_fingerprint(body.host_key or "") or (body.host_key or "").strip(),
        insecure=body.insecure_host_key,
        judges_dir=body.judges_dir.rstrip("/") or "/",
        web_url=body.web_url or "",
        web_login=(body.web_login or "").strip(),
        web_password=body.web_password or stored_web,
        allowed_contests=parse_contests(body.allowed_contests),
        cxx=settings.EJUDGE_CXX,
        package_type=settings.EJUDGE_PACKAGE_TYPE,
    )


async def check_connection(config: EjudgeConfig) -> dict:
    """SSH login + the judges dir exists; serve-control login (a warning only). Never raises."""
    if not config.host_key and not config.insecure:
        fingerprint = await fingerprint_probe(config)
        if not fingerprint:
            return {"ok": False, "error": f"не удалось подключиться к {config.ssh_host}:{config.ssh_port} по SSH",
                    "host_key_fingerprint": None, "warnings": []}
        return {
            "ok": False,
            "error": "сервер предъявил ключ хоста "
                     f"{fingerprint}: сверьте его с ключом на сервере ejudge и вставьте в поле «Ключ хоста»",
            "host_key_fingerprint": fingerprint,
            "warnings": [],
        }
    warnings: list[str] = []
    try:
        async with host_factory(config) as host:  # type: ignore[attr-defined]
            result = await host.run(f"test -d {q(config.judges_dir)} && echo ok")
            if result.exit_status != 0 or "ok" not in result.stdout:
                return {"ok": False, "error": f"на сервере нет каталога {config.judges_dir}",
                        "host_key_fingerprint": None, "warnings": []}
    except EjudgeError as e:
        return {"ok": False, "error": str(e), "host_key_fingerprint": None, "warnings": []}
    if config.web_reload:
        try:
            await web_factory(config.web_url, config.web_login, config.web_password).check_login()
        except EjudgeError as e:
            warnings.append(f"веб-интерфейс: {e}")
    else:
        warnings.append("веб-интерфейс не задан: после экспорта конфигурацию контеста придётся перезагружать вручную")
    return {"ok": True, "error": None, "host_key_fingerprint": None, "warnings": warnings}


def _status(account: EjudgeAccount | None) -> dict:
    server = server_config()
    if account is None:
        return {"linked": False, "server_configured": server.configured}
    return {
        "linked": True,
        "server_configured": server.configured,
        "ssh_host": account.ssh_host,
        "ssh_port": account.ssh_port,
        "ssh_user": account.ssh_user,
        "auth_method": account.auth_method,
        "host_key": account.host_key,
        "insecure_host_key": account.insecure_host_key,
        "judges_dir": account.judges_dir,
        "web_url": account.web_url,
        "web_login": account.web_login,
        "has_web_password": bool(account.web_password_enc),
        "has_key_passphrase": bool(account.ssh_key_passphrase_enc),
        "allowed_contests": account.allowed_contests,
        "updated_at": account.updated_at.isoformat() if account.updated_at else None,
    }


@integrations_router.get("/ejudge")
async def ejudge_status(user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    return _status(await db.get(EjudgeAccount, user_id))


@integrations_router.post("/ejudge/test")
async def ejudge_test(
    body: EjudgeLinkIn, user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    """Check the connection described by the form (nothing is saved)."""
    return await check_connection(_config_from(body, await db.get(EjudgeAccount, user_id)))


@integrations_router.post("/ejudge")
async def ejudge_link(
    body: EjudgeLinkIn, user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)
) -> dict:
    """Save the integration (after a successful connection check unless ``verify`` is false)."""
    account = await db.get(EjudgeAccount, user_id)
    config = _config_from(body, account)
    if not config.host_key and not config.insecure:
        raise HTTPException(
            status_code=400,
            detail="укажите ключ хоста (нажмите «Проверить подключение», чтобы увидеть отпечаток) "
                   "или явно отключите его проверку",
        )
    warnings: list[str] = []
    if body.verify:
        check = await check_connection(config)
        if not check["ok"]:
            raise HTTPException(status_code=400, detail=check["error"])
        warnings = check["warnings"]

    if account is None:
        account = EjudgeAccount(user_id=user_id)
        db.add(account)
    account.ssh_host = config.ssh_host
    account.ssh_port = config.ssh_port
    account.ssh_user = config.ssh_user
    account.auth_method = body.auth_method
    account.ssh_secret_enc = encrypt(config.ssh_key if body.auth_method == "key" else config.ssh_password)
    account.ssh_key_passphrase_enc = encrypt_optional(config.ssh_key_passphrase)
    account.host_key = config.host_key or None
    account.insecure_host_key = config.insecure
    account.judges_dir = config.judges_dir
    account.web_url = config.web_url or None
    account.web_login = config.web_login or None
    account.web_password_enc = encrypt_optional(config.web_password)
    account.allowed_contests = ",".join(str(c) for c in sorted(config.allowed_contests))
    await db.commit()
    await db.refresh(account)
    return {**_status(account), "warnings": warnings}


@integrations_router.post("/ejudge/unlink")
async def ejudge_unlink(user_id: int = Depends(get_current_user), db: AsyncSession = Depends(get_db)) -> dict:
    account = await db.get(EjudgeAccount, user_id)
    if account is not None:
        await db.delete(account)
        await db.commit()
    return _status(None)
