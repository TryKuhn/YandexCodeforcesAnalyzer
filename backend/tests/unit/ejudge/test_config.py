"""Where an export goes: the user's ejudge integration vs the server's EJUDGE_* settings."""
import asyncssh
import pytest

import api.user.ejudge.export as export
import api.user.ejudge.router as router
from api.crypt.secrets import encrypt
from api.user.ejudge import config as ejudge_config
from api.user.ejudge.common import EjudgeError
from api.user.ejudge.config import EjudgeConfig
from api.user.ejudge.remote import _FingerprintClient, _known_hosts_text, connect_options
from models.user.integrations import EjudgeAccount
from settings import settings
from tests.unit.ejudge.helpers import SERVE_CFG, FakeHost
from tests.unit.ejudge.test_export import FakeWeb, polygon  # noqa: F401 - fixture

KEY = asyncssh.generate_private_key("ssh-ed25519")


@pytest.fixture
def server(monkeypatch):
    monkeypatch.setattr(settings, "EJUDGE_SSH_HOST", "server.ejudge")
    monkeypatch.setattr(settings, "EJUDGE_JUDGES_DIR", "/home/judges")
    monkeypatch.setattr(settings, "EJUDGE_URL", "https://server/cgi-bin")
    monkeypatch.setattr(settings, "EJUDGE_LOGIN", "admin")
    monkeypatch.setattr(settings, "EJUDGE_PASSWORD", "pw")
    monkeypatch.setattr(settings, "EJUDGE_GVALUER_PATH", "/opt/gvaluer")
    monkeypatch.setattr(settings, "EJUDGE_ALLOWED_CONTESTS", "")


async def link(db, user, **overrides) -> EjudgeAccount:
    values = dict(
        user_id=user.id, ssh_host="my.ejudge", ssh_port=2222, ssh_user="ej", auth_method="password",
        ssh_secret_enc=encrypt("ssh-pass"), host_key="SHA256:abc", judges_dir="/srv/judges",
        web_url="https://my/cgi-bin", web_login="me", web_password_enc=encrypt("web-pass"),
        allowed_contests="42,43",
    )
    values.update(overrides)
    account = EjudgeAccount(**values)
    db.add(account)
    await db.commit()
    return account


async def test_server_settings_without_an_account(server, db, user):
    config = await ejudge_config.resolve(user.id, db)
    assert config.source == "server" and config.ssh_host == "server.ejudge" and config.configured
    assert config.gvaluer_path == "/opt/gvaluer" and config.web_reload


async def test_user_account_wins_and_is_decrypted(server, db, user):
    await link(db, user)
    config = await ejudge_config.resolve(user.id, db)
    assert config.source == "user" and config.ssh_host == "my.ejudge" and config.ssh_port == 2222
    assert config.ssh_password == "ssh-pass" and config.ssh_key == ""
    assert config.web_password == "web-pass" and config.allowed_contests == {42, 43}
    assert config.judges_dir == "/srv/judges"
    # the server's gvaluer binary lives on the server's host, not on the user's one
    assert config.gvaluer_path == ""


async def test_unreadable_secret_is_an_ejudge_error(server, db, user):
    await link(db, user, ssh_secret_enc="garbage")
    with pytest.raises(EjudgeError, match="интеграция ejudge"):
        await ejudge_config.resolve(user.id, db)
    status = await router.route_status(user_id=user.id, db=db)
    assert status["configured"] is False and "интеграция ejudge" in status["error"]


async def test_export_uses_the_users_ejudge(polygon, server, db, user):  # noqa: F811
    await link(db, user)
    contest = "/srv/judges/000042"
    host = FakeHost({f"{contest}/conf/serve.cfg": SERVE_CFG.encode()})
    FakeWeb.calls = []
    report = await export.run_export(export.ExportRequest(polygon_id=555, contest_id=42), user.id, db,
                                     host_factory=host, web_factory=FakeWeb)
    assert host.configs[0].source == "user" and host.configs[0].ssh_host == "my.ejudge"
    assert report["problem_dir"].startswith(f"{contest}/problems/")
    assert FakeWeb.calls == [(("https://my/cgi-bin", "me", "web-pass"), 42)]
    # no server gvaluer binary: it is compiled from source on the user's host
    assert "gvaluer.cpp" in host.tree(report["problem_dir"])

    with pytest.raises(EjudgeError, match="разрешённых контестов интеграции"):
        await export.run_export(export.ExportRequest(polygon_id=555, contest_id=7), user.id, db,
                                host_factory=host, web_factory=FakeWeb)


async def test_not_configured_points_to_the_profile(monkeypatch, db, user):
    monkeypatch.setattr(settings, "EJUDGE_SSH_HOST", "")
    status = await router.route_status(user_id=user.id, db=db)
    assert status["configured"] is False and status["source"] == "server"
    with pytest.raises(EjudgeError, match="профиле"):
        await export.run_export(export.ExportRequest(polygon_id=1, contest_id=1), user.id, db)


# --------------------------------------------------------------------------- ssh options
def user_config(**kw) -> EjudgeConfig:
    return EjudgeConfig(source="user", ssh_host="h", **kw)


def test_key_auth_with_fingerprint_pins_the_host_key():
    pem = KEY.export_private_key().decode()
    options = connect_options(user_config(ssh_key=pem, host_key="SHA256:xyz"))
    assert options["client_keys"][0].get_fingerprint() == KEY.get_fingerprint()
    assert "password" not in options and options["agent_path"] is None
    client = options["client_factory"]()
    assert isinstance(client, _FingerprintClient)
    assert client.validate_host_public_key("h", "1.2.3.4", 22, KEY) is False
    good = _FingerprintClient(KEY.get_fingerprint("sha256"))
    assert good.validate_host_public_key("h", "1.2.3.4", 22, KEY) is True


def test_encrypted_key_needs_its_passphrase():
    pem = KEY.export_private_key(passphrase="pp").decode()
    assert connect_options(user_config(ssh_key=pem, ssh_key_passphrase="pp", insecure=True))["client_keys"]
    with pytest.raises(EjudgeError, match="приватный ключ"):
        connect_options(user_config(ssh_key=pem, insecure=True))


def test_password_auth_and_known_hosts_line():
    public = KEY.export_public_key().decode().strip()
    options = connect_options(user_config(ssh_password="pw", host_key=public))
    assert options["password"] == "pw" and options["client_keys"] is None
    assert options["known_hosts"] is not None
    assert _known_hosts_text(public) == f"* {public}\n"
    assert _known_hosts_text(f"# c\nmy.host {public}") == f"my.host {public}\n"


def test_host_key_is_required_unless_explicitly_insecure():
    with pytest.raises(EjudgeError, match="ключ хоста"):
        connect_options(user_config(ssh_password="pw"))
    assert connect_options(user_config(ssh_password="pw", insecure=True))["known_hosts"] is None
    server = EjudgeConfig(source="server", ssh_host="h", ssh_key_path="/run/key")
    with pytest.raises(EjudgeError, match="EJUDGE_SSH_KNOWN_HOSTS"):
        connect_options(server)
    options = connect_options(EjudgeConfig(source="server", ssh_host="h", ssh_key_path="/k", known_hosts_path="/kh"))
    assert options["client_keys"] == ["/k"] and options["known_hosts"] == "/kh"
