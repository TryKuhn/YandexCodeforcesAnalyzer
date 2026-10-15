"""Access to the ejudge host over SSH/SFTP (asyncssh).

Connect as the user ejudge runs under (usually ``ejudge``), so the uploaded
files are readable by the judging daemons. Host keys are verified against
``EJUDGE_SSH_KNOWN_HOSTS``; ``EJUDGE_SSH_INSECURE=true`` turns the check off
explicitly (never by default).
"""
from __future__ import annotations

import posixpath
import shlex
from dataclasses import dataclass
from typing import Any, Protocol

from api.user.ejudge.common import EjudgeError


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


class SSHHost:
    """``async with SSHHost(settings) as host: ...``"""

    def __init__(self, settings) -> None:  # type: ignore[no-untyped-def]
        self.settings = settings
        self._conn: Any = None
        self._sftp: Any = None

    async def __aenter__(self) -> SSHHost:
        import asyncssh

        s = self.settings
        if s.EJUDGE_SSH_KNOWN_HOSTS:
            known_hosts: object = s.EJUDGE_SSH_KNOWN_HOSTS
        elif s.EJUDGE_SSH_INSECURE:
            known_hosts = None
        else:
            raise EjudgeError(
                "не задан EJUDGE_SSH_KNOWN_HOSTS (проверка ключа хоста ejudge); "
                "для отключения проверки явно задайте EJUDGE_SSH_INSECURE=true"
            )
        try:
            self._conn = await asyncssh.connect(
                s.EJUDGE_SSH_HOST,
                port=s.EJUDGE_SSH_PORT,
                username=s.EJUDGE_SSH_USER,
                client_keys=[s.EJUDGE_SSH_KEY_PATH] if s.EJUDGE_SSH_KEY_PATH else None,
                known_hosts=known_hosts,
                connect_timeout=20,
            )
            self._sftp = await self._conn.start_sftp_client()
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
        import asyncssh

        assert self._sftp is not None
        try:
            async with self._sftp.open(path, "rb") as f:
                data = await f.read()
        except (OSError, asyncssh.SFTPError) as e:
            raise EjudgeError(f"не удалось прочитать {path}: {e}") from e
        return data.decode("utf-8", errors="replace")

    async def write_files(self, base: str, files: dict[str, bytes]) -> None:
        import asyncssh

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
        import asyncssh

        assert self._sftp is not None
        try:
            await self._sftp.posix_rename(src, dst)
        except (OSError, asyncssh.SFTPError) as e:
            raise EjudgeError(f"не удалось переименовать {src} в {dst}: {e}") from e

    async def run(self, command: str) -> CommandResult:
        import asyncssh

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
