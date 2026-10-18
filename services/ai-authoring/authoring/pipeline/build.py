"""Package build with automatic repair.

A full build with verification is started (the backend commits first) and the
new package is polled until READY or FAILED. On failure the error goes to the
model together with the problem materials; its fix is applied and the build is
restarted. After ``MAX_REPAIR_ATTEMPTS`` failed repairs the error is handed to
the user and the run ends as ``needs_user``.
"""
from __future__ import annotations

import asyncio
import logging
import time

from sqlalchemy import update

from authoring.db import utcnow
from authoring.llm import prompts
from authoring.llm.client import LLMError
from authoring.llm.protocol import parse
from authoring.models import Build
from authoring.pipeline.apply import apply_edits
from authoring.pipeline.context import PipelineError, RunCancelled, RunContext
from authoring.polygon.client import PolygonError
from authoring.settings import settings

logger = logging.getLogger(__name__)

# what a repair may touch: everything the build depends on (plus the statement
# for broken samples), but never the tags
REPAIR_TARGETS = frozenset({
    "solution", "validator", "checker", "interactor", "generator", "script", "limits", "samples", "statement",
})

_ALREADY_BUILDING = ("already", "уже")


async def _package_ids(ctx: RunContext) -> set[int]:
    packages = await ctx.client.packages(ctx.session.polygon_id)
    return {p["id"] for p in packages if p.get("id") is not None}


async def _start_build(ctx: RunContext) -> set[int]:
    """Start a build; returns the package ids that existed before it."""
    before = await _package_ids(ctx)
    for attempt in range(3):
        try:
            await ctx.client.build_package(ctx.session.polygon_id, full=True, verify=True)
            return before
        except PolygonError as e:
            if any(m in e.message.lower() for m in _ALREADY_BUILDING) and attempt < 2:
                await ctx.step("Polygon уже собирает пакет, жду…")
                await asyncio.sleep(settings.BUILD_POLL_SECONDS * 3)
                before = await _package_ids(ctx)
                continue
            raise
    return before


async def _wait(ctx: RunContext, build: Build, before: set[int]) -> tuple[str, str]:
    """Poll until our package is READY / FAILED; (state, comment)."""
    deadline = time.monotonic() + settings.BUILD_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        await asyncio.sleep(settings.BUILD_POLL_SECONDS)
        try:
            packages = await ctx.client.packages(ctx.session.polygon_id)
        except PolygonError as e:
            logger.info("packages poll failed: %s", e.message)
            await ctx.heartbeat()
            continue
        fresh = [p for p in packages if p.get("id") is not None and p["id"] not in before]
        if not fresh:
            await ctx.step(f"Сборка пакета (попытка {build.attempt}): ожидание Polygon")
            continue
        package = max(fresh, key=lambda p: p["id"])
        state = package.get("state") or "PENDING"
        if build.package_id != package["id"] or build.state != state:
            build.package_id = package["id"]
            build.state = state
            build.updated_at = utcnow()
            await ctx.db.commit()
        if state in ("READY", "FAILED"):
            return state, package.get("comment") or ""
        label = "в очереди" if state == "PENDING" else "собирается"
        await ctx.step(f"Пакет #{package['id']} {label} (попытка {build.attempt})")
    return "TIMEOUT", f"Пакет не собрался за {settings.BUILD_TIMEOUT_SECONDS // 60} минут"


async def _repair(ctx: RunContext, error: str, attempt: int, previous: list[str]) -> str | None:
    """One repair: returns a short description of the fix, None when nothing was changed."""
    dossier = await ctx.dossier(refresh=True)
    completion = await ctx.llm.complete(ctx.model, prompts.repair_messages(dossier, error, attempt, previous))
    parsed = parse(completion.text)
    if not parsed.edits:
        return None
    result = await apply_edits(ctx, parsed.edits, allowed=set(REPAIR_TARGETS),
                               commit_message=f"AI: build repair #{attempt}")
    if not result.changed:
        return None
    fix = ", ".join(result.changed)
    note = parsed.reply.strip().splitlines()[0] if parsed.reply.strip() else ""
    await ctx.say(
        f"Попытка починки {attempt}: {note}\n\n{result.report()}",
        intent="repair", changed=result.changed, errors=result.errors,
    )
    return f"{fix}: {note}" if note else fix


async def run_build(ctx: RunContext) -> dict:
    current: list[int] = []  # id of the Build row in progress
    try:
        return await _run_build(ctx, current)
    except BaseException as e:
        # a cancelled/failed run must not leave its build "RUNNING" forever
        if current:
            await ctx.db.rollback()
            await ctx.db.execute(
                update(Build)
                .where(Build.id == current[-1], Build.state.not_in(("READY", "FAILED", "TIMEOUT", "ERROR")))
                .values(state="CANCELLED" if isinstance(e, RunCancelled) else "ERROR", updated_at=utcnow())
            )
            await ctx.db.commit()
        raise


async def _run_build(ctx: RunContext, current: list[int]) -> dict:
    max_repairs = int((ctx.run.payload or {}).get("max_repairs", settings.MAX_REPAIR_ATTEMPTS))
    previous_fixes: list[str] = []
    attempt = 1
    while True:
        build = Build(session_id=ctx.session.id, run_id=ctx.run.id, attempt=attempt, state="STARTING")
        ctx.db.add(build)
        await ctx.db.commit()
        current.append(build.id)
        await ctx.step(f"Запуск сборки пакета (попытка {attempt})", done=attempt - 1, total=max_repairs + 1)

        try:
            before = await _start_build(ctx)
        except PolygonError as e:
            build.state, build.comment = "ERROR", e.message
            await ctx.db.commit()
            raise PipelineError(f"Polygon не запустил сборку: {e.message}")

        state, comment = await _wait(ctx, build, before)

        def outcome(
            *, _state: str = state, _package: int | None = build.package_id, _attempt: int = attempt,
            **extra: object,
        ) -> dict:
            # "changed": the repairs applied to the problem files on the way
            return {"state": _state, "package_id": _package, "attempts": _attempt,
                    "changed": list(previous_fixes), **extra}

        build.state, build.comment = state, comment
        await ctx.db.commit()
        ctx.invalidate()

        if state == "READY":
            repaired = f" (после {attempt - 1} починок)" if attempt > 1 else ""
            text = f"Пакет #{build.package_id} собран{repaired}."
            await ctx.step(text)
            await ctx.say(text, intent="build", package_id=build.package_id, state=state)
            await ctx.notify("build", text, [{"kind": "package", "text": text, "package_id": build.package_id,
                                              "state": state}])
            await ctx.snapshot(refresh=True)
            return outcome()

        error = comment or state
        if state == "TIMEOUT":
            minutes = settings.BUILD_TIMEOUT_SECONDS // 60
            text = f"Сборка пакета не завершилась за {minutes} минут. Проверьте её в Polygon."
            await ctx.say(text, intent="build", is_error=True, package_id=build.package_id, state=state)
            await ctx.notify("build", "Сборка пакета не завершилась", [{"kind": "package", "text": text,
                                                                       "package_id": build.package_id,
                                                                       "state": state}])
            return outcome(needs_user=True, error=text)
        if attempt > max_repairs:
            text = (
                f"Пакет не собирается и после {max_repairs} попыток автоматической починки. "
                f"Нужна ваша помощь.\n\nОшибка Polygon:\n```\n{error[:4000]}\n```"
            )
            await ctx.say(text, intent="build", is_error=True, package_id=build.package_id, state=state)
            await ctx.notify("build", "Сборка пакета не удалась", [{"kind": "package", "text": error[:300],
                                                                    "package_id": build.package_id,
                                                                    "state": state}])
            await ctx.snapshot(refresh=True)
            return outcome(needs_user=True, error=error[:4000])

        await ctx.step(f"Сборка упала, чиню (попытка {attempt} из {max_repairs})")
        try:
            fix = await _repair(ctx, error, attempt, previous_fixes)
        except LLMError as e:
            fix = None
            logger.warning("repair LLM failed: %s", e.message)
        if fix is None:
            text = (
                "Сборка упала, и модель не смогла предложить исправление.\n\n"
                f"Ошибка Polygon:\n```\n{error[:4000]}\n```"
            )
            await ctx.say(text, intent="build", is_error=True, package_id=build.package_id, state=state)
            await ctx.notify("build", "Сборка пакета не удалась", [{"kind": "package", "text": error[:300],
                                                                    "package_id": build.package_id,
                                                                    "state": state}])
            return outcome(needs_user=True, error=error[:4000])
        previous_fixes.append(fix)
        attempt += 1
