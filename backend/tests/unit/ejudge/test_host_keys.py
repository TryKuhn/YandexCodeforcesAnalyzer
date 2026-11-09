"""Host key pinning against a real SSH server with several host keys (RSA + ECDSA + ED25519)."""
from __future__ import annotations

import asyncssh
import pytest

from api.user.ejudge.common import EjudgeError
from api.user.ejudge.config import EjudgeConfig
from api.user.ejudge.remote import (
    SSHHost,
    host_key_fingerprint,
    normalize_fingerprint,
    normalize_private_key,
    server_host_keys,
)

CLIENT = asyncssh.generate_private_key("ssh-ed25519")
HOST_KEYS = {
    "RSA": asyncssh.generate_private_key("ssh-rsa"),
    "ECDSA": asyncssh.generate_private_key("ecdsa-sha2-nistp256"),
    "ED25519": asyncssh.generate_private_key("ssh-ed25519"),
}


def fp(key: asyncssh.SSHKey) -> str:
    return str(key.get_fingerprint("sha256"))


@pytest.fixture
async def ssh_server():
    server = await asyncssh.listen(
        "127.0.0.1", 0,
        server_host_keys=list(HOST_KEYS.values()),  # RSA first: what the server prefers is not what admins copy
        authorized_client_keys=asyncssh.import_authorized_keys(CLIENT.export_public_key().decode()),
        sftp_factory=True,
    )
    yield server.sockets[0].getsockname()[1]
    server.close()


def config(port: int, host_key: str, **kw) -> EjudgeConfig:
    kw.setdefault("ssh_key", CLIENT.export_private_key().decode())
    return EjudgeConfig(source="user", ssh_host="127.0.0.1", ssh_port=port, ssh_user="ejudge", host_key=host_key, **kw)


async def connects(cfg: EjudgeConfig) -> bool:
    async with SSHHost(cfg) as host:
        return host._sftp is not None


async def test_any_of_the_servers_host_keys_can_be_pinned(ssh_server):
    for key_type, key in HOST_KEYS.items():
        assert await connects(config(ssh_server, fp(key))), key_type
    # as `ssh-keygen -l` prints it, or with padding
    assert await connects(config(ssh_server, f"256 {fp(HOST_KEYS['ED25519'])} root@ejudge (ED25519)"))
    assert await connects(config(ssh_server, fp(HOST_KEYS["RSA"]) + "="))


async def test_the_fingerprint_shown_is_the_ed25519_one(ssh_server):
    cfg = config(ssh_server, "")
    assert await host_key_fingerprint(cfg) == fp(HOST_KEYS["ED25519"])
    assert await server_host_keys(cfg) == [(t, fp(HOST_KEYS[t])) for t in ("ED25519", "ECDSA", "RSA")]


async def test_wrong_fingerprint_lists_the_servers_keys(ssh_server):
    other = fp(asyncssh.generate_private_key("ssh-ed25519"))
    with pytest.raises(EjudgeError) as e:
        await connects(config(ssh_server, other))
    assert other in str(e.value) and fp(HOST_KEYS["ED25519"]) in str(e.value) and "RSA" in str(e.value)


async def test_the_login_keys_fingerprint_in_the_host_key_field(ssh_server):
    with pytest.raises(EjudgeError, match="отпечаток вашего ключа для входа"):
        await connects(config(ssh_server, fp(CLIENT)))


async def test_wrong_user_names_it(ssh_server):
    cfg = config(ssh_server, fp(HOST_KEYS["ED25519"]), ssh_key=asyncssh.generate_private_key(
        "ssh-ed25519").export_private_key().decode())
    with pytest.raises(EjudgeError, match="ejudge@127.0.0.1"):
        await connects(cfg)


async def test_mangled_key_paste_still_works(ssh_server):
    pem = CLIENT.export_private_key().decode()
    lines = pem.strip().splitlines()
    for mangled in (
        " ".join(lines),  # newlines lost
        "\n".join("    " + line for line in lines),  # indented
        pem.replace("\n", " \n", 2),  # non-breaking spaces
    ):
        assert await connects(config(ssh_server, fp(HOST_KEYS["ED25519"]), ssh_key=mangled))
    with pytest.raises(EjudgeError, match="вставьте ключ целиком"):
        await connects(config(ssh_server, fp(HOST_KEYS["ED25519"]), ssh_key=pem[:200]))


def test_normalizers():
    assert normalize_fingerprint("nothing here") is None
    assert normalize_fingerprint("SHA256:" + "A" * 43 + "=") == "SHA256:" + "A" * 43
    encrypted = "-----BEGIN RSA PRIVATE KEY-----\nProc-Type: 4,ENCRYPTED\n\nabc\n-----END RSA PRIVATE KEY-----\n"
    assert normalize_private_key(encrypted) == encrypted
