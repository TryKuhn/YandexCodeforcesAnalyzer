"""Exporting a Polygon problem into an ejudge contest.

1. download the latest READY (or the given) full package of the problem;
2. read the contest's ``serve.cfg`` over SFTP (score system, existing problems);
3. build the problem directory, ``[problem]`` section and ``valuer.cfg``
   (:mod:`api.user.ejudge.convert`);
4. upload into a staging directory, compile the checker / interactor / gvaluer
   there, then swap it with the old directory (kept as a backup);
5. back up and rewrite ``serve.cfg``;
6. reload the contest configuration through the web interface.

A preview runs steps 1-3 only.
"""
from __future__ import annotations

import logging
import posixpath
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from api.user.ejudge.common import EjudgeError, is_configured
from api.user.ejudge.convert import MANAGED_KEYS, build_plan
from api.user.ejudge.package import PolygonPackage, parse_package
from api.user.ejudge.remote import EjudgeHost, SSHHost, q
from api.user.ejudge.servecfg import ServeCfg, summary
from api.user.ejudge.web import EjudgeWeb
from api.user.polygon import methods
from api.user.polygon.client import PolygonAPIError
from settings import settings

logger = logging.getLogger(__name__)

JOB_TYPE = "ejudge.export"
PACKAGE_TYPES = ("linux", "windows", "standard")

Progress = Callable[[int], Awaitable[None]]
HostFactory = Callable[[object], EjudgeHost]


async def _no_progress(_: int) -> None:
    return None


@dataclass
class ExportRequest:
    polygon_id: int
    contest_id: int
    package_id: int | None = None
    short_name: str | None = None
    problem_id: int | None = None
    internal_name: str | None = None


def contest_dir(contest_id: int) -> str:
    return posixpath.join(settings.EJUDGE_JUDGES_DIR, f"{contest_id:06d}")


def serve_cfg_path(contest_id: int) -> str:
    return posixpath.join(contest_dir(contest_id), "conf", "serve.cfg")


def require_configured() -> None:
    if not is_configured(settings):
        raise EjudgeError("экспорт в ejudge не настроен (EJUDGE_SSH_HOST, EJUDGE_JUDGES_DIR)")


def require_allowed(contest_id: int) -> None:
    allowed = settings.ejudge_allowed_contests
    if allowed and contest_id not in allowed:
        raise EjudgeError(f"контест {contest_id} не входит в EJUDGE_ALLOWED_CONTESTS")


async def fetch_package(
    polygon_id: int, package_id: int | None, user_id: int, db: AsyncSession
) -> tuple[int, PolygonPackage]:
    """The package (latest READY by default), as a parsed full package."""
    packages = await methods.get_packages(polygon_id, user_id, db)
    ready = [p for p in packages if p.get("state") == "READY" and p.get("id") is not None]
    if package_id is None:
        if not ready:
            raise EjudgeError("у задачи нет собранного пакета (READY): сначала соберите пакет")
        package_id = max(p["id"] for p in ready)
    elif not any(p["id"] == package_id for p in ready):
        raise EjudgeError(f"пакет #{package_id} не найден среди собранных")

    errors: list[str] = []
    preferred = settings.EJUDGE_PACKAGE_TYPE
    for package_type in dict.fromkeys((preferred, *PACKAGE_TYPES)):
        try:
            data = await methods.download_package(
                polygon_id, package_id, user_id, db, package_type=package_type
            )
            return package_id, parse_package(data)
        except (PolygonAPIError, EjudgeError) as e:
            errors.append(f"{package_type}: {e}")
    raise EjudgeError("не удалось скачать полный пакет: " + "; ".join(errors))


async def read_contest(host: EjudgeHost, contest_id: int) -> ServeCfg:
    return ServeCfg(await host.read_text(serve_cfg_path(contest_id)))


async def contest_info(contest_id: int, host_factory: HostFactory = SSHHost) -> dict:
    require_configured()
    require_allowed(contest_id)
    async with host_factory(settings) as host:  # type: ignore[attr-defined]
        cfg = await read_contest(host, contest_id)
    return {
        "contest_id": contest_id,
        "score_system": cfg.score_system,
        "advanced_layout": cfg.advanced_layout,
        "problems": summary(cfg),
    }


async def _cleanup(host: EjudgeHost, path: str | None, command: str | None = None) -> None:
    """Best effort: a failed cleanup must not hide the original error."""
    try:
        await host.run(command or f"rm -rf {q(path or '')}")
    except Exception:  # noqa: BLE001
        logger.warning("ejudge cleanup failed: %s", command or path, exc_info=True)


async def _check(host: EjudgeHost, command: str, what: str) -> str:
    result = await host.run(command)
    if result.exit_status != 0:
        raise EjudgeError(f"{what}: {(result.stderr or result.stdout).strip()[:3000]}")
    return result.stdout


async def run_export(
    request: ExportRequest,
    user_id: int,
    db: AsyncSession,
    *,
    dry_run: bool = False,
    progress: Progress = _no_progress,
    host_factory: HostFactory = SSHHost,
    web_factory: Callable[[str, str, str], EjudgeWeb] = EjudgeWeb,
) -> dict:
    require_configured()
    require_allowed(request.contest_id)
    await progress(5)
    package_id, package = await fetch_package(request.polygon_id, request.package_id, user_id, db)
    await progress(30)

    async with host_factory(settings) as host:  # type: ignore[attr-defined]
        cfg = await read_contest(host, request.contest_id)
        plan = build_plan(
            package, cfg,
            polygon_id=request.polygon_id,
            short_name=request.short_name,
            problem_id=request.problem_id,
            internal_name=request.internal_name,
            gvaluer_binary=settings.EJUDGE_GVALUER_PATH,
        )
        report = {**plan.report(), "package_id": package_id, "contest_id": request.contest_id}
        if dry_run:
            return {**report, "dry_run": True}
        await progress(40)

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        problems_dir = posixpath.join(contest_dir(request.contest_id), "problems")
        final = posixpath.join(problems_dir, plan.internal_name)
        staging = posixpath.join(problems_dir, f".{plan.internal_name}.upload-{stamp}")
        backup = posixpath.join(problems_dir, f".{plan.internal_name}.bak-{stamp}")

        try:
            await host.write_files(staging, plan.files)
            await progress(70)
            if plan.valuer_cfg is not None and settings.EJUDGE_GVALUER_PATH:
                await _check(host, f"cp {q(settings.EJUDGE_GVALUER_PATH)} {q(staging + '/gvaluer')}",
                             "копирование gvaluer")
            for executable, source in plan.compile:
                await _check(
                    host,
                    f"cd {q(staging)} && {settings.EJUDGE_CXX} -o {q(executable)} {q(source)}",
                    f"компиляция {source} на сервере ejudge",
                )
            await progress(85)

            # serve.cfg may have been edited meanwhile (by a person or another export):
            # re-read it right before changing anything and make sure the plan still holds
            serve = serve_cfg_path(request.contest_id)
            fresh = await read_contest(host, request.contest_id)
            if fresh.text() != cfg.text():
                again = build_plan(
                    package, fresh,
                    polygon_id=request.polygon_id,
                    short_name=request.short_name,
                    problem_id=request.problem_id,
                    internal_name=request.internal_name,
                    gvaluer_binary=settings.EJUDGE_GVALUER_PATH,
                )
                if (again.internal_name, again.problem_id, again.short_name, again.score_system) != (
                    plan.internal_name, plan.problem_id, plan.short_name, plan.score_system
                ):
                    raise EjudgeError("serve.cfg контеста изменился во время экспорта: повторите экспорт")
                plan, cfg = again, fresh
            await _check(host, f"cp -p {q(serve)} {q(serve + '.bak-' + stamp)}", "резервная копия serve.cfg")
        except BaseException:
            await _cleanup(host, staging)
            raise

        await _check(
            host,
            f"if [ -e {q(final)} ]; then mv {q(final)} {q(backup)}; fi && mv {q(staging)} {q(final)} "
            f"&& chmod -R a+rX {q(final)}",
            "замена каталога задачи",
        )
        try:
            existing = cfg.find_problem(extid=f"polygon:{request.polygon_id}", problem_id=plan.problem_id)
            cfg.upsert_problem(existing, plan.section, MANAGED_KEYS)
            for key, value in plan.contest_globals.items():
                cfg.set_global(key, value)
            tmp = f"{serve}.tmp-{stamp}"
            await host.write_text(tmp, cfg.text())
            await host.rename(tmp, serve)
        except BaseException:
            # put the old problem directory back so it matches the untouched serve.cfg
            await _cleanup(
                host, None,
                f"rm -rf {q(final)} && if [ -e {q(backup)} ]; then mv {q(backup)} {q(final)}; fi",
            )
            raise
    await progress(95)

    report["problem_dir"] = final
    report["backup_dir"] = backup
    report["reloaded"] = False
    if settings.EJUDGE_URL and settings.EJUDGE_LOGIN:
        try:
            await web_factory(settings.EJUDGE_URL, settings.EJUDGE_LOGIN, settings.EJUDGE_PASSWORD) \
                .reload_config(request.contest_id)
            report["reloaded"] = True
        except EjudgeError as e:
            report["warnings"] = [*report["warnings"], f"конфигурация не перезагружена: {e}"]
    else:
        report["warnings"] = [*report["warnings"], "EJUDGE_URL/EJUDGE_LOGIN не заданы: перезагрузите конфигурацию "
                              "контеста в ejudge вручную"]
    await progress(100)
    return report


def make_handler(session_factory, host_factory: HostFactory = SSHHost):  # type: ignore[no-untyped-def]
    """Job handler; failures are returned (not raised) so the job is not retried blindly."""

    async def handler(payload: dict, progress: Progress) -> dict:
        request = ExportRequest(**payload["request"])
        async with session_factory() as db:
            try:
                result = await run_export(
                    request, int(payload["user_id"]), db, progress=progress, host_factory=host_factory
                )
            except (EjudgeError, PolygonAPIError) as e:
                logger.info("ejudge export of %s failed: %s", request.polygon_id, e)
                return {"ok": False, "error": str(e), "request": asdict(request)}
            except Exception as e:  # noqa: BLE001 -- reported to the user instead of a blind retry
                logger.exception("ejudge export of %s crashed", request.polygon_id)
                return {"ok": False, "error": f"внутренняя ошибка экспорта: {e!r}"[:1000],
                        "request": asdict(request)}
        return {"ok": True, **result}

    return handler
