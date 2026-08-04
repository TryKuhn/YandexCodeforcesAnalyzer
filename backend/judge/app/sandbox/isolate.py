"""isolate-backed sandbox, where the strict defaults live."""

import asyncio
import tempfile
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from pathlib import Path

from .base import Sandbox, SandboxError, SandboxSession
from .limits import RunLimits
from .meta import build_result
from .pool import BoxPool
from .result import RunResult, RunStatus

# isolate exits 1 when the program failed but the run is valid, 2 when isolate broke
_ISOLATE_INTERNAL_EXIT = 2

# inheriting the judge environment would leak host paths and worker credentials
_BASE_ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/box"}


def _ms_to_s(value: int) -> str:
    return f"{value / 1000:.3f}"


class IsolateSession(SandboxSession):
    def __init__(self, box_id: int, box_dir: Path, isolate_bin: str, use_cgroups: bool) -> None:
        self._box_id = box_id
        self._box_dir = box_dir
        self._isolate_bin = isolate_bin
        self._use_cgroups = use_cgroups

    @property
    def box_dir(self) -> Path:
        return self._box_dir

    def _resolve(self, name: str) -> Path:
        """Map a name to a path inside the box, refusing to escape it."""
        target = (self._box_dir / name).resolve()
        box_root = self._box_dir.resolve()
        if target != box_root and box_root not in target.parents:
            raise SandboxError(f"path escapes the box: {name}")
        return target

    async def put_file(self, name: str, data: bytes, *, executable: bool = False) -> None:
        path = self._resolve(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        if executable:
            path.chmod(0o755)

    async def read_file(self, name: str, *, max_bytes: int | None = None) -> bytes:
        path = self._resolve(name)
        if not path.exists():
            return b""
        if max_bytes is None:
            return path.read_bytes()
        with path.open("rb") as handle:
            return handle.read(max_bytes)

    async def run(
        self,
        argv: Sequence[str],
        limits: RunLimits,
        *,
        stdin: str | None = None,
        stdout: str | None = None,
        stderr: str | None = None,
        env: Mapping[str, str] | None = None,
        writable: bool = False,
    ) -> RunResult:
        if not argv:
            raise SandboxError("argv must not be empty")

        # meta lives outside the box: a program that could rewrite it could fake its verdict
        with tempfile.NamedTemporaryFile(suffix=".meta", delete=False) as handle:
            meta_path = Path(handle.name)

        try:
            command = self._build_command(
                argv, limits, meta_path, stdin, stdout, stderr, env, writable
            )
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, isolate_stderr = await process.communicate()

            meta_text = meta_path.read_text() if meta_path.exists() else ""
            if process.returncode == _ISOLATE_INTERNAL_EXIT and not meta_text:
                message = isolate_stderr.decode(errors="replace").strip()
                return RunResult(
                    status=RunStatus.INTERNAL_ERROR,
                    message=message or "isolate failed",
                )
            return build_result(meta_text, limits)
        finally:
            meta_path.unlink(missing_ok=True)

    def _build_command(
        self,
        argv: Sequence[str],
        limits: RunLimits,
        meta_path: Path,
        stdin: str | None,
        stdout: str | None,
        stderr: str | None,
        env: Mapping[str, str] | None,
        writable: bool,
    ) -> list[str]:
        command = [self._isolate_bin, f"--box-id={self._box_id}"]
        if self._use_cgroups:
            command.append("--cg")

        command += [
            f"--meta={meta_path}",
            f"--time={_ms_to_s(limits.cpu_time_ms)}",
            f"--wall-time={_ms_to_s(limits.effective_wall_time_ms)}",
            f"--extra-time={_ms_to_s(limits.extra_time_ms)}",
            f"--processes={limits.max_processes}",
            f"--fsize={limits.output_kb}",
        ]

        # cgroup memory counts the whole tree, so forking cannot dodge the limit
        if self._use_cgroups:
            command.append(f"--cg-mem={limits.memory_kb}")
        else:
            command.append(f"--mem={limits.memory_kb}")

        if limits.stack_kb:
            command.append(f"--stack={limits.stack_kb}")
        if stdin:
            command.append(f"--stdin={stdin}")
        if stdout:
            command.append(f"--stdout={stdout}")
        if stderr:
            command.append(f"--stderr={stderr}")

        for key, value in {**_BASE_ENV, **(env or {})}.items():
            command.append(f"--env={key}={value}")

        # compilation needs to write, a contestant's run never does
        if writable:
            command.append("--dir=/box=/box:rw")

        command += ["--run", "--"]
        command.extend(argv)
        return command


class IsolateSandbox(Sandbox):
    """Creates and destroys isolate boxes."""

    def __init__(
        self,
        pool: BoxPool,
        *,
        isolate_bin: str = "isolate",
        use_cgroups: bool = True,
    ) -> None:
        self._pool = pool
        self._isolate_bin = isolate_bin
        self._use_cgroups = use_cgroups

    @asynccontextmanager
    async def session(self) -> AsyncIterator[SandboxSession]:
        async with self._pool.lease() as box_id:
            box_dir = await self._init_box(box_id)
            try:
                yield IsolateSession(box_id, box_dir, self._isolate_bin, self._use_cgroups)
            finally:
                # must run even after a failure, or the next contestant inherits these files
                await self._cleanup_box(box_id)

    def _base_command(self, box_id: int) -> list[str]:
        command = [self._isolate_bin, f"--box-id={box_id}"]
        if self._use_cgroups:
            command.append("--cg")
        return command

    async def _init_box(self, box_id: int) -> Path:
        try:
            process = await asyncio.create_subprocess_exec(
                *self._base_command(box_id),
                "--init",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            # misconfigured host, not a broken submission
            raise SandboxError(f"isolate binary not found: {self._isolate_bin}") from exc
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise SandboxError(
                f"isolate --init failed for box {box_id}: "
                f"{stderr.decode(errors='replace').strip()}"
            )
        # isolate prints the box root, the writable working dir is <root>/box
        return Path(stdout.decode().strip()) / "box"

    async def _cleanup_box(self, box_id: int) -> None:
        try:
            process = await asyncio.create_subprocess_exec(
                *self._base_command(box_id),
                "--cleanup",
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
            )
        except FileNotFoundError:
            self._pool.retire(box_id)
            return
        await process.communicate()
        # do not raise, we may already be handling another failure
        if process.returncode != 0:
            self._pool.retire(box_id)
