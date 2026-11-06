"""``/api/integrations/ejudge``: link (with a connection check), test, status, unlink."""
import pytest
from fastapi import HTTPException

import api.user.integrations.ejudge as ej
from api.crypt.secrets import decrypt
from api.user.ejudge.common import EjudgeError
from api.user.ejudge.remote import CommandResult
from models.user.integrations import EjudgeAccount


class Host:
    """Fake SSH host: ``test -d <dir>`` succeeds for ``dirs``."""

    def __init__(self, dirs=("/home/judges",), fail=None):
        self.dirs, self.fail, self.configs = dirs, fail, []

    def __call__(self, config):
        self.configs.append(config)
        return self

    async def __aenter__(self):
        if self.fail:
            raise EjudgeError(self.fail)
        return self

    async def __aexit__(self, *exc):
        return None

    async def run(self, command):
        ok = any(f"test -d {d} " in command.replace("'", "") for d in self.dirs)
        return CommandResult(0 if ok else 1, "ok\n" if ok else "", "")


class Web:
    fail = None

    def __init__(self, url, login, password):
        self.args = (url, login, password)

    async def check_login(self):
        if Web.fail:
            raise EjudgeError(Web.fail)


@pytest.fixture
def fakes(monkeypatch):
    host = Host()
    Web.fail = None
    monkeypatch.setattr(ej, "host_factory", host)
    monkeypatch.setattr(ej, "web_factory", Web)

    async def probe(config):
        return "SHA256:server-key"

    monkeypatch.setattr(ej, "fingerprint_probe", probe)
    return host


def form(**kw):
    values = dict(ssh_host="ejudge.example.org", auth_method="password", ssh_password="pw",
                  host_key="SHA256:server-key", web_url="https://ejudge.example.org/cgi-bin/",
                  web_login="admin", web_password="wp", allowed_contests="42, 43")
    values.update(kw)
    return ej.EjudgeLinkIn(**values)


async def test_link_saves_encrypted_and_status_hides_secrets(fakes, db, user):
    result = await ej.ejudge_link(form(), user_id=user.id, db=db)
    assert result["linked"] and result["warnings"] == []
    account = await db.get(EjudgeAccount, user.id)
    assert account.ssh_secret_enc != "pw" and decrypt(account.ssh_secret_enc) == "pw"
    assert decrypt(account.web_password_enc) == "wp"
    assert account.web_url == "https://ejudge.example.org/cgi-bin" and account.allowed_contests == "42,43"
    status = await ej.ejudge_status(user_id=user.id, db=db)
    text = repr(status)
    assert status["linked"] and status["auth_method"] == "password" and status["has_web_password"]
    assert "pw" not in text.replace("password", "").replace("has_web_", "")
    assert fakes.configs[-1].ssh_password == "pw"


async def test_resaving_without_secrets_keeps_them(fakes, db, user):
    await ej.ejudge_link(form(), user_id=user.id, db=db)
    await ej.ejudge_link(form(ssh_password=None, web_password=None, ssh_port=2222), user_id=user.id, db=db)
    account = await db.get(EjudgeAccount, user.id)
    assert account.ssh_port == 2222 and decrypt(account.ssh_secret_enc) == "pw"
    assert decrypt(account.web_password_enc) == "wp"
    # switching to a key requires the key
    with pytest.raises(HTTPException) as e:
        await ej.ejudge_link(form(auth_method="key", ssh_password=None), user_id=user.id, db=db)
    assert "приватный ключ" in e.value.detail


async def test_missing_host_key_shows_the_fingerprint(fakes, db, user):
    result = await ej.ejudge_test(form(host_key=None), user_id=user.id, db=db)
    assert result["ok"] is False and result["host_key_fingerprint"] == "SHA256:server-key"
    with pytest.raises(HTTPException) as e:
        await ej.ejudge_link(form(host_key=None), user_id=user.id, db=db)
    assert e.value.status_code == 400 and "ключ хоста" in e.value.detail
    # an explicit opt-out is accepted
    saved = await ej.ejudge_link(form(host_key=None, insecure_host_key=True), user_id=user.id, db=db)
    assert saved["insecure_host_key"] is True


async def test_failed_check_is_not_saved(fakes, db, user, monkeypatch):
    monkeypatch.setattr(ej, "host_factory", Host(fail="ejudge отклонил вход по SSH"))
    with pytest.raises(HTTPException) as e:
        await ej.ejudge_link(form(), user_id=user.id, db=db)
    assert "отклонил вход" in e.value.detail
    assert await db.get(EjudgeAccount, user.id) is None
    result = await ej.ejudge_test(form(judges_dir="/nope"), user_id=user.id, db=db)
    assert result["ok"] is False


async def test_missing_judges_dir_and_web_warning(fakes, db, user):
    result = await ej.ejudge_test(form(judges_dir="/nope"), user_id=user.id, db=db)
    assert result["ok"] is False and "/nope" in result["error"]
    Web.fail = "ejudge: не удалось войти в serve-control"
    result = await ej.ejudge_test(form(), user_id=user.id, db=db)
    assert result["ok"] is True and "serve-control" in result["warnings"][0]
    result = await ej.ejudge_test(form(web_url=None, web_login=None), user_id=user.id, db=db)
    assert "вручную" in result["warnings"][0]


async def test_unlink(fakes, db, user):
    await ej.ejudge_link(form(), user_id=user.id, db=db)
    assert (await ej.ejudge_unlink(user_id=user.id, db=db))["linked"] is False
    assert await db.get(EjudgeAccount, user.id) is None


def test_form_validation():
    with pytest.raises(ValueError):
        form(ssh_host="host; rm -rf /")
    with pytest.raises(ValueError):
        form(judges_dir="relative/dir")
    with pytest.raises(ValueError):
        form(web_url="ftp://x")
    with pytest.raises(ValueError):
        form(allowed_contests="1, two")
