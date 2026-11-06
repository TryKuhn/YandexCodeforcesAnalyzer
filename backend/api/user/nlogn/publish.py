"""Publishing a Polygon problem to NlogN (job ``nlogn.publish``).

NlogN judges its "ejudge" problems on the same ejudge the export writes to, so
a publication is:

1. the ejudge export of the package into the contest (``api.user.ejudge.export``);
2. the NlogN statement built from the same package (``api.user.nlogn.statement``);
3. ``push`` mode (from this app): creating/updating the NlogN problem bound to
   ``<ejudge contest>:<ejudge problem>`` with the user's NlogN token, optionally
   adding it to an NlogN contest; ``pull`` mode (the NlogN admin asked through
   the public API): the payload is the job result and NlogN saves it itself.

Every publication is remembered (:class:`NlognPublication`) to prefill the next
one and to tell the NlogN admin where a problem already lives.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.user.ejudge import export
from api.user.ejudge.common import EjudgeError
from api.user.ejudge.export import ExportRequest, HostFactory
from api.user.ejudge.remote import SSHHost
from api.user.ejudge.web import EjudgeWeb
from api.user.integrations.nlogn import NlognClient, NlognError, client_for, problem_admin_url
from api.user.nlogn.statement import build_statement
from api.user.polygon.client import PolygonAPIError
from models.user.integrations import NlognPublication
from settings import settings

logger = logging.getLogger(__name__)

JOB_TYPE = "nlogn.publish"
MODES = ("push", "pull")

Progress = Callable[[int], Awaitable[None]]
ClientFactory = Callable[[int, AsyncSession], Awaitable[NlognClient]]


async def _no_progress(_: int) -> None:
    return None


@dataclass
class PublishRequest:
    polygon_id: int
    ejudge_contest_id: int
    short_name: str | None = None
    package_id: int | None = None
    title: str | None = None
    nlogn_contest_id: int | None = None
    mode: str = "push"


def problem_url(polygon_id: int) -> str:
    return f"{settings.public_url}/tasks/{polygon_id}"


async def save_publication(db: AsyncSession, user_id: int, result: dict) -> NlognPublication:
    """Upsert by (user, polygon problem, ejudge contest)."""
    row = (await db.execute(select(NlognPublication).where(
        NlognPublication.user_id == user_id,
        NlognPublication.polygon_id == result["polygon_id"],
        NlognPublication.ejudge_contest_id == result["ejudge_contest_id"],
    ))).scalars().first()
    if row is None:
        row = NlognPublication(user_id=user_id, polygon_id=result["polygon_id"],
                               ejudge_contest_id=result["ejudge_contest_id"])
        db.add(row)
    row.package_id = result.get("package_id")
    row.revision = result.get("revision")
    row.ejudge_problem_id = int(result["ejudge_problem_id"])
    row.short_name = str(result["short_name"])[:32]
    row.title = str(result.get("title") or "")[:255]
    nlogn = result.get("nlogn") or {}
    if nlogn.get("problem_id"):
        row.nlogn_problem_id = int(nlogn["problem_id"])
    if (nlogn.get("contest") or {}).get("id"):
        row.nlogn_contest_id = int(nlogn["contest"]["id"])
    await db.commit()
    return row


async def latest_publication(db: AsyncSession, user_id: int, polygon_id: int) -> NlognPublication | None:
    return (await db.execute(
        select(NlognPublication)
        .where(NlognPublication.user_id == user_id, NlognPublication.polygon_id == polygon_id)
        .order_by(NlognPublication.updated_at.desc(), NlognPublication.id.desc())
        .limit(1)
    )).scalars().first()


def publication_out(row: NlognPublication, nlogn_base_url: str | None = None) -> dict:
    return {
        "polygon_id": row.polygon_id,
        "package_id": row.package_id,
        "revision": row.revision,
        "ejudge_contest_id": row.ejudge_contest_id,
        "ejudge_problem_id": row.ejudge_problem_id,
        "short_name": row.short_name,
        "title": row.title,
        "nlogn_problem_id": row.nlogn_problem_id,
        "nlogn_contest_id": row.nlogn_contest_id,
        "nlogn_problem_url": problem_admin_url(nlogn_base_url, row.nlogn_problem_id)
        if nlogn_base_url and row.nlogn_problem_id else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


async def run_publish(
    request: PublishRequest,
    user_id: int,
    db: AsyncSession,
    *,
    progress: Progress = _no_progress,
    host_factory: HostFactory = SSHHost,
    web_factory: Callable[[str, str, str], EjudgeWeb] = EjudgeWeb,
    nlogn_client: ClientFactory = client_for,
) -> dict:
    if request.mode not in MODES:
        raise EjudgeError(f"неизвестный режим публикации {request.mode!r}")
    client = None
    if request.mode == "push":
        # fail before the (slow) export when NlogN is not linked
        try:
            client = await nlogn_client(user_id, db)
        except NlognError as e:
            raise EjudgeError(str(e)) from e

    async def export_progress(percent: int) -> None:
        await progress(int(percent * 0.8))

    fetched: dict = {}
    report = await export.run_export(
        ExportRequest(polygon_id=request.polygon_id, contest_id=request.ejudge_contest_id,
                      package_id=request.package_id, short_name=request.short_name),
        user_id, db, progress=export_progress, host_factory=host_factory, web_factory=web_factory,
        fetched=fetched,
    )
    package = fetched["package"]
    warnings: list[str] = list(report.get("warnings") or [])
    statement = build_statement(package, warnings)
    await progress(85)

    title = (request.title or statement.title or package.name("russian", "english")).strip()[:255]
    result: dict = {
        "ejudge_contest_id": request.ejudge_contest_id,
        "ejudge_problem_id": int(report["problem_id"]),
        "short_name": report["short_name"],
        "title": title,
        "html_statement": statement.html,
        "text_statement": statement.text,
        "statement_language": statement.language,
        "statement_source": statement.source,
        "time_limit_ms": package.time_limit_ms,
        "memory_limit_mb": package.memory_limit_bytes // (1024 * 1024),
        "polygon_id": request.polygon_id,
        "package_id": report.get("package_id"),
        "revision": package.revision,
        "url": problem_url(request.polygon_id),
        "ejudge_reloaded": bool(report.get("reloaded")),
        "warnings": warnings,
    }

    if client is not None:
        payload = {
            "ejudgeContestId": result["ejudge_contest_id"],
            "ejudgeProblemId": result["ejudge_problem_id"],
            "title": title,
            "htmlStatement": statement.html,
            "textStatement": statement.text,
            "source": {"system": "taskforge", "polygonId": request.polygon_id,
                       "packageId": result["package_id"], "revision": package.revision, "url": result["url"]},
        }
        if request.nlogn_contest_id:
            payload["addToContestId"] = request.nlogn_contest_id
        try:
            answer = await client.upsert_ejudge_problem(payload)
        except NlognError as e:
            # the ejudge part is done: remember it, then report the NlogN failure
            await save_publication(db, user_id, result)
            raise EjudgeError(f"задача выгружена в ejudge (контест {result['ejudge_contest_id']}, "
                              f"задача {result['ejudge_problem_id']}), но NlogN её не принял: {e}") from e
        problem = (answer or {}).get("problem") or {}
        contest = (answer or {}).get("contest") or None
        result["nlogn"] = {
            "problem_id": problem.get("id"),
            "title": problem.get("title"),
            "foreign_problem_identifier": problem.get("foreignProblemIdentifier"),
            "created": bool((answer or {}).get("created")),
            "url": problem_admin_url(client.base_url, problem["id"]) if problem.get("id") else None,
            "contest": contest,
        }
    await save_publication(db, user_id, result)
    await progress(100)
    return result


def make_handler(session_factory, host_factory: HostFactory = SSHHost,  # type: ignore[no-untyped-def]
                 nlogn_client: ClientFactory = client_for):
    """Job handler; like the export, failures are returned (``ok: false``), not retried blindly."""

    async def handler(payload: dict, progress: Progress) -> dict:
        request = PublishRequest(**payload["request"])
        async with session_factory() as db:
            try:
                result = await run_publish(request, int(payload["user_id"]), db, progress=progress,
                                           host_factory=host_factory, nlogn_client=nlogn_client)
            except (EjudgeError, PolygonAPIError, NlognError) as e:
                logger.info("NlogN publication of %s failed: %s", request.polygon_id, e)
                return {"ok": False, "error": str(e), "request": asdict(request)}
            except Exception as e:  # noqa: BLE001 -- reported to the user instead of a blind retry
                logger.exception("NlogN publication of %s crashed", request.polygon_id)
                return {"ok": False, "error": f"внутренняя ошибка публикации: {e!r}"[:1000],
                        "request": asdict(request)}
        return {"ok": True, **result}

    return handler
