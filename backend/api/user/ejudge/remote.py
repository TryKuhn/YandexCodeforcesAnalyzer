"""Access to the ejudge host over SSH/SFTP (asyncssh).

Connect as the user ejudge runs under (usually ``ejudge``), so the uploaded
files are readable by the judging daemons. Where to connect comes from an
:class:`~api.user.ejudge.config.EjudgeConfig` (the user's integration or the
server's EJUDGE_* settings). The host key is always verified -- against a
SHA256 fingerprint, known_hosts lines or a known_hosts file -- unless the check
was turned off explicitly (never by default).
"""
from __future__ import annotations

import posixpath
import shlex
from dataclasses import dataclass
from typing import Any, Protocol

import asyncssh

from api.user.ejudge.common import EjudgeError
from api.user.ejudge.config import EjudgeConfig


@dataclass
class CommandResult:
    exit_status: int
    stdout: str
    stderr: str


class EjudgeHost(Protocol):
    async def read_text(self, path: str) -> str: ...

    async def write_files(self, base: str, files: dict[str, bytes]) -> None: ...

    async def write_text(self, path: str, text: str) -> None: ...

    async def run(self, command: str) -> CommandResult: ...

    async def rename(self, src: str, dst: str) -> None: ...


def _known_hosts_text(text: str) -> str:
    """known_hosts lines; a bare public key ("ssh-ed25519 AAAA...") matches any host name."""
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        first = line.split()[0]
        if first.startswith(("ssh-", "ecdsa-", "sk-")):
            line = f"* {line}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def is_fingerprint(text: str) -> bool:
    return text.strip().startswith("SHA256:")


def connect_options(config: EjudgeConfig) -> dict[str, Any]:
    """asyncssh.connect() keyword arguments for ``config`` (raises EjudgeError when unusable)."""
    options: dict[str, Any] = {
        "port": config.ssh_port,
        "username": config.ssh_user,
        "connect_timeout": 20,
        # never pick up keys of the container user or an ssh-agent by accident
        "agent_path": None,
    }
    if config.ssh_key:
        try:
            options["client_keys"] = [
                asyncssh.import_private_key(config.ssh_key, config.ssh_key_passphrase or None)
            ]
        except (asyncssh.KeyImportError, ValueError) as e:
            raise EjudgeError(f"не удалось прочитать приватный ключ SSH: {e}") from e
    elif config.ssh_key_path:
        options["client_keys"] = [config.ssh_key_path]
    else:
        options["client_keys"] = None
    if config.ssh_password:
        options["password"] = config.ssh_password

    host_key = config.host_key.strip()
    if host_key and is_fingerprint(host_key):
        # checked by _FingerprintClient during the handshake, before any credentials are sent
        options["known_hosts"] = asyncssh.import_known_hosts("")
        options["server_host_key_algs"] = "default"
        options["client_factory"] = lambda: _FingerprintClient(host_key)
    elif host_key:
        try:
            options["known_hosts"] = asyncssh.import_known_hosts(_known_hosts_text(host_key))
        except (ValueError, asyncssh.Error) as e:
            raise EjudgeError(f"не удалось разобрать ключ хоста (known_hosts): {e}") from e
    elif config.known_hosts_path:
        options["known_hosts"] = config.known_hosts_path
    elif config.insecure:
        options["known_hosts"] = None
    else:
        raise EjudgeError(
            "не задан ключ хоста ejudge (отпечаток SHA256:... или строка known_hosts); "
            "чтобы отключить проверку, явно разрешите это в настройках интеграции"
            if config.source == "user" else
            "не задан EJUDGE_SSH_KNOWN_HOSTS (проверка ключа хоста ejudge); "
            "для отключения проверки явно задайте EJUDGE_SSH_INSECURE=true"
        )
    return options


class _FingerprintClient(asyncssh.SSHClient):
    """Accepts exactly one server host key, given by its SHA256 fingerprint."""

    def __init__(self, fingerprint: str) -> None:
        self.fingerprint = fingerprint.strip()

    def validate_host_public_key(self, host, addr, port, key) -> bool:  # type: ignore[no-untyped-def]
        return bool(key.get_fingerprint("sha256") == self.fingerprint)


class _RecordingClient(asyncssh.SSHClient):
    """Rejects every host key but remembers its fingerprint (to show it to the user)."""

    def __init__(self) -> None:
        self.seen: str | None = None

    def validate_host_public_key(self, host, addr, port, key) -> bool:  # type: ignore[no-untyped-def]
        self.seen = key.get_fingerprint("sha256")
        return False


async def host_key_fingerprint(config: EjudgeConfig) -> str | None:
    """The SHA256 fingerprint of the server's host key (no authentication is attempted)."""
    client = _RecordingClient()
    try:
        conn = await asyncssh.connect(
            config.ssh_host, port=config.ssh_port, username=config.ssh_user,
            known_hosts=asyncssh.import_known_hosts(""), server_host_key_algs="default",
            client_factory=lambda: client, client_keys=None, agent_path=None, connect_timeout=20,
        )
        conn.close()
    except (OSError, asyncssh.Error):
        pass
    return client.seen


class SSHHost:
    """``async with SSHHost(config) as host: ...``"""

    def __init__(self, config: EjudgeConfig) -> None:
        self.config = config
        self._conn: Any = None
        self._sftp: Any = None

    async def __aenter__(self) -> SSHHost:
        options = connect_options(self.config)
        try:
            self._conn = await asyncssh.connect(self.config.ssh_host, **options)
            self._sftp = await self._conn.start_sftp_client()
        except asyncssh.HostKeyNotVerifiable as e:
            raise EjudgeError(f"ключ хоста ejudge не совпадает с сохранённым: {e}") from e
        except asyncssh.PermissionDenied as e:
            raise EjudgeError(f"ejudge отклонил вход по SSH (проверьте пользователя, ключ или пароль): {e}") from e
        except (OSError, asyncssh.Error) as e:
            raise EjudgeError(f"не удалось подключиться к ejudge по SSH: {e}") from e
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._sftp is not None:
            self._sftp.exit()
        if self._conn is not None:
            self._conn.close()
            await self._conn.wait_closed()

    async def read_text(self, path: str) -> str:
        assert self._sftp is not None
        try:
            async with self._sftp.open(path, "rb") as f:
                data = await f.read()
        except (OSError, asyncssh.SFTPError) as e:
            raise EjudgeError(f"не удалось прочитать {path}: {e}") from e
        return data.decode("utf-8", errors="replace")

    async def write_files(self, base: str, files: dict[str, bytes]) -> None:
        assert self._sftp is not None
        try:
            dirs = sorted({posixpath.dirname(posixpath.join(base, rel)) for rel in files})
            for d in dirs:
                await self._sftp.makedirs(d, exist_ok=True)
            for rel, content in files.items():
                async with self._sftp.open(posixpath.join(base, rel), "wb") as f:
                    await f.write(content)
        except (OSError, asyncssh.SFTPError) as e:
            raise EjudgeError(f"не удалось записать файлы в {base}: {e}") from e

    async def write_text(self, path: str, text: str) -> None:
        await self.write_files(posixpath.dirname(path), {posixpath.basename(path): text.encode()})

    async def rename(self, src: str, dst: str) -> None:
        """Atomic replace (POSIX rename) of ``dst``."""
        assert self._sftp is not None
        try:
            await self._sftp.posix_rename(src, dst)
        except (OSError, asyncssh.SFTPError) as e:
            raise EjudgeError(f"не удалось переименовать {src} в {dst}: {e}") from e

    async def run(self, command: str) -> CommandResult:
        assert self._conn is not None
        try:
            result = await self._conn.run(command, check=False, timeout=300)
        except asyncssh.TimeoutError as e:
            raise EjudgeError(f"команда на сервере ejudge не завершилась за 300 с: {command[:200]}") from e
        except (OSError, asyncssh.Error) as e:
            raise EjudgeError(f"ошибка SSH при выполнении команды: {e}") from e
        return CommandResult(
            exit_status=result.exit_status if result.exit_status is not None else -1,
            stdout=str(result.stdout or ""),
            stderr=str(result.stderr or ""),
        )


def q(path: str) -> str:
    return shlex.quote(path)
