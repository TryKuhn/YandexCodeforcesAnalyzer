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
import re
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


_FINGERPRINT_RE = re.compile(r"SHA256:([A-Za-z0-9+/]{43})=?")

# host key algorithms by key type, in OpenSSH's order of preference: a server with several
# host keys (RSA + ECDSA + ED25519 is the default) shows ED25519 first, as `ssh` does --
# that is the fingerprint admins usually copy
HOST_KEY_TYPES: dict[str, tuple[str, ...]] = {
    "ED25519": ("ssh-ed25519",),
    "ECDSA": ("ecdsa-sha2-nistp256", "ecdsa-sha2-nistp384", "ecdsa-sha2-nistp521"),
    "RSA": ("rsa-sha2-512", "rsa-sha2-256", "ssh-rsa"),
}
PREFERRED_HOST_KEY_ALGS = [alg for algs in HOST_KEY_TYPES.values() for alg in algs]


def normalize_fingerprint(text: str) -> str | None:
    """``SHA256:...`` from a pasted fingerprint, also from ``ssh-keygen -l`` output
    (``256 SHA256:... comment (ED25519)``) or with base64 padding; None if there is none."""
    m = _FINGERPRINT_RE.search(text or "")
    return f"SHA256:{m.group(1)}" if m else None


def is_fingerprint(text: str) -> bool:
    return normalize_fingerprint(text) is not None


_PEM_RE = re.compile(r"(-----BEGIN [A-Z0-9 ]+-----)(.*?)(-----END [A-Z0-9 ]+-----)", re.S)


def normalize_private_key(text: str) -> str:
    """The key with its body re-flowed: pasting from a chat or a document often adds indents,
    non-breaking spaces or glues the lines together. Keys with PEM headers
    (``Proc-Type: ...``) are returned as they are."""
    m = _PEM_RE.search(text.replace("\u00a0", " "))
    if m is None or ":" in m.group(2):
        return text
    body = "".join(m.group(2).split())
    lines = [body[i:i + 70] for i in range(0, len(body), 70)]
    return "\n".join([m.group(1), *lines, m.group(3)]) + "\n"


def _import_key(text: str, passphrase: str | None) -> asyncssh.SSHKey:
    try:
        return asyncssh.import_private_key(text, passphrase)
    except (asyncssh.KeyImportError, ValueError) as first:
        fixed = normalize_private_key(text)
        if fixed == text:
            raise first
        return asyncssh.import_private_key(fixed, passphrase)


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
            options["client_keys"] = [_import_key(config.ssh_key, config.ssh_key_passphrase or None)]
        except (asyncssh.KeyImportError, ValueError) as e:
            raise EjudgeError(f"не удалось прочитать приватный ключ SSH ({e}): вставьте ключ целиком, "
                              "от строки -----BEGIN ... до -----END ...") from e
    elif config.ssh_key_path:
        options["client_keys"] = [config.ssh_key_path]
    else:
        options["client_keys"] = None
    if config.ssh_password:
        options["password"] = config.ssh_password

    host_key = config.host_key.strip()
    fingerprint = normalize_fingerprint(host_key)
    if not fingerprint and "SHA256:" in host_key:
        raise EjudgeError(f"не похоже на отпечаток ключа хоста: {host_key[:80]!r} "
                          "(нужно SHA256: и 43 символа, как печатает ssh-keygen -l)")
    if fingerprint:
        # checked by _FingerprintClient during the handshake, before any credentials are sent
        options["known_hosts"] = asyncssh.import_known_hosts("")
        options["server_host_key_algs"] = PREFERRED_HOST_KEY_ALGS
        options["client_factory"] = lambda: _FingerprintClient(fingerprint)
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
        self.fingerprint = normalize_fingerprint(fingerprint) or fingerprint.strip()

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
            known_hosts=asyncssh.import_known_hosts(""), server_host_key_algs=PREFERRED_HOST_KEY_ALGS,
            client_factory=lambda: client, client_keys=None, agent_path=None, connect_timeout=20,
        )
        conn.close()
    except (OSError, asyncssh.Error):
        pass
    return client.seen


async def server_host_keys(config: EjudgeConfig) -> list[tuple[str, str]]:
    """``[(key type, SHA256 fingerprint)]`` of every host key the server has (no authentication)."""
    found: list[tuple[str, str]] = []
    for key_type, algs in HOST_KEY_TYPES.items():
        client = _RecordingClient()
        try:
            conn = await asyncssh.connect(
                config.ssh_host, port=config.ssh_port, username=config.ssh_user,
                known_hosts=asyncssh.import_known_hosts(""), server_host_key_algs=list(algs),
                client_factory=lambda: client, client_keys=None, agent_path=None, connect_timeout=20,
            )
            conn.close()
        except OSError:
            break  # unreachable: the other types would only wait for the same timeout
        except asyncssh.Error:
            pass
        if client.seen:
            found.append((key_type, client.seen))
    return found


def _client_key_fingerprint(config: EjudgeConfig) -> str | None:
    if not config.ssh_key:
        return None
    try:
        return str(_import_key(config.ssh_key, config.ssh_key_passphrase or None).get_fingerprint("sha256"))
    except (asyncssh.KeyImportError, ValueError):
        return None


async def host_key_mismatch(config: EjudgeConfig) -> list[str]:
    """For a pinned fingerprint the server did not show first: the host key algorithms of the
    server's key with that fingerprint (to connect again); a clear EjudgeError if there is none."""
    pinned = normalize_fingerprint(config.host_key)
    if pinned is None:
        raise EjudgeError("ключ хоста ejudge не совпадает с сохранённым (known_hosts): "
                          "сверьте ключ сервера и обновите поле «Ключ хоста»")
    keys = await server_host_keys(config)
    for key_type, fingerprint in keys:
        if fingerprint == pinned:
            return list(HOST_KEY_TYPES[key_type])
    shown = ", ".join(f"{key_type} {fingerprint}" for key_type, fingerprint in keys) or "не удалось получить"
    if pinned == _client_key_fingerprint(config):
        raise EjudgeError(
            f"в поле «Ключ хоста» указан отпечаток вашего ключа для входа ({pinned}), а нужен отпечаток "
            f"ключа самого сервера. Ключи сервера {config.ssh_host}: {shown}. Сверьте с администратором "
            "(на сервере: ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub)"
        )
    raise EjudgeError(
        f"ключ хоста ejudge не совпадает с указанным {pinned}. Ключи сервера {config.ssh_host}: {shown}. "
        "Сверьте с администратором (на сервере: ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub)"
    )


class SSHHost:
    """``async with SSHHost(config) as host: ...``"""

    def __init__(self, config: EjudgeConfig) -> None:
        self.config = config
        self._conn: Any = None
        self._sftp: Any = None

    async def __aenter__(self) -> SSHHost:
        options = connect_options(self.config)
        where = f"{self.config.ssh_user}@{self.config.ssh_host}:{self.config.ssh_port}"
        try:
            try:
                self._conn = await asyncssh.connect(self.config.ssh_host, **options)
            except asyncssh.HostKeyNotVerifiable:
                # the pinned key may be another of the server's keys (e.g. RSA while ED25519 was offered)
                algs = await host_key_mismatch(self.config)
                self._conn = await asyncssh.connect(self.config.ssh_host, **{**options, "server_host_key_algs": algs})
            self._sftp = await self._conn.start_sftp_client()
        except EjudgeError:
            raise
        except asyncssh.HostKeyNotVerifiable as e:
            raise EjudgeError(f"ключ хоста ejudge не совпадает с сохранённым: {e}") from e
        except asyncssh.PermissionDenied as e:
            raise EjudgeError(
                f"ejudge отклонил вход {where} по SSH: проверьте имя пользователя (ключ выдан для него?), "
                f"ключ или пароль ({e})"
            ) from e
        except (OSError, asyncssh.Error) as e:
            raise EjudgeError(
                f"не удалось подключиться к {where} по SSH: {e or type(e).__name__}. Если сервер доступен "
                "только из определённых сетей, попросите администратора открыть SSH для сервера TaskForge"
            ) from e
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
