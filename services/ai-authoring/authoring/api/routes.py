"""HTTP API (``/api/ai``); the backend proxies these paths to the service.

Long work (chat answers, edits, generation, builds) is a *run*: the request
stores it and returns at once, the worker executes it, the UI polls
``/sessions/{id}/state`` for new messages, notifications, the active run and
the latest build.
"""
from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from authoring.api.schemas import (
    CheckerValidatorIn,
    CreateProblemIn,
    EventsSeenIn,
    GenerateIn,
    GroupsIn,
    MessageIn,
    PlanIn,
    SessionPatch,
    SolutionDraftIn,
    build_out,
    event_out,
    message_out,
    run_out,
    session_out,
)
from authoring.auth import get_current_user
from authoring.db import get_db, utcnow
from authoring.llm.client import LLM, LLMError
from authoring.llm.client import llm as default_llm
from authoring.llm.models import DEFAULT_MODEL, MAIN_MODELS, ROUTER_MODELS, normalize_model
from authoring.models import ACTIVE_RUN_STATUSES, AuthoringSession, Build, Event, Message, Run, RunKind, RunStatus
from authoring.pipeline import assist
from authoring.pipeline.groups import (
    PlanError,
    build_script,
    expand_lines,
    normalize_plan,
    plan_from_snapshot,
    scoring_section,
)
from authoring.pipeline.runner import enqueue
from authoring.polygon.client import PolygonClient, PolygonError
from authoring.sync.dossier import build_dossier
from authoring.sync.service import has_active_run, load_snapshot, sync_session
from authoring.sync.snapshot import SnapshotError

router = APIRouter(prefix="/api/ai")

MESSAGE_PAGE = 300


def get_llm() -> LLM:
    return default_llm


def get_client_factory() -> Callable[[int], PolygonClient]:
    return PolygonClient


# --------------------------------------------------------------------------- helpers
async def _session(db: AsyncSession, session_id: str, user_id: int) -> AuthoringSession:
    session = await db.get(AuthoringSession, session_id)
    if session is None or session.user_id != user_id:
        raise HTTPException(status_code=404, detail="Сессия не найдена")
    return session


async def _get_or_create(db: AsyncSession, user_id: int, polygon_id: int, *, model: str | None = None,
                         problem_type: str | None = None) -> AuthoringSession:
    query = select(AuthoringSession).where(
        AuthoringSession.user_id == user_id, AuthoringSession.polygon_id == polygon_id
    )
    session = (await db.execute(query)).scalars().first()
    if session is not None:
        return session
    session = AuthoringSession(
        user_id=user_id, polygon_id=polygon_id, model=normalize_model(model),
        problem_type=problem_type or "regular", settings={"auto_build": True},
    )
    db.add(session)
    try:
        await db.commit()
    except IntegrityError:  # opened in two tabs at once
        await db.rollback()
        session = (await db.execute(query)).scalars().first()
        if session is None:
            raise
    return session


async def _active_run(db: AsyncSession, session_id: str) -> Run | None:
    rows = (await db.execute(
        select(Run).where(Run.session_id == session_id, Run.status.in_(ACTIVE_RUN_STATUSES))
        .order_by(Run.created_at)
    )).scalars().all()
    running = [r for r in rows if r.status == RunStatus.RUNNING.value]
    candidates = running or list(rows)
    return candidates[0] if candidates else None


async def _latest_build(db: AsyncSession, session_id: str) -> Build | None:
    return (await db.execute(
        select(Build).where(Build.session_id == session_id).order_by(Build.id.desc()).limit(1)
    )).scalars().first()


def _plan_or_422(raw: dict):  # type: ignore[no-untyped-def]
    try:
        return normalize_plan(raw)
    except PlanError as e:
        raise HTTPException(status_code=422, detail=f"План групп: {e}")


# --------------------------------------------------------------------------- models
@router.get("/models")
async def route_models() -> dict:
    return {
        "default": DEFAULT_MODEL,
        "router": list(ROUTER_MODELS),
        "models": [
            {"id": m.id, "name": m.name, "vendor": m.vendor, "price_in": m.price_in, "price_out": m.price_out,
             "context": m.context}
            for m in MAIN_MODELS
        ],
    }


# --------------------------------------------------------------------------- problems
@router.post("/problems")
async def route_create_problem(
    body: CreateProblemIn,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    client_factory: Callable[[int], PolygonClient] = Depends(get_client_factory),
) -> dict:
    """Create a clean Polygon problem and its session; with an idea, start generation."""
    if body.plan is not None:
        _plan_or_422(body.plan)
    client = client_factory(user_id)
    try:
        polygon_id = await client.create_problem(body.name.strip())
        if body.problem_type == "interactive":
            await client.update_info(polygon_id, interactive=True)
    except PolygonError as e:
        raise HTTPException(status_code=e.status if e.status and e.status < 500 else 502, detail=e.message)
    session = await _get_or_create(db, user_id, polygon_id, model=body.model, problem_type=body.problem_type)
    run = None
    if body.idea and body.idea.strip():
        db.add(Message(session_id=session.id, role="user", content=body.idea.strip(), meta={"intent": "generate"}))
        await db.commit()
        run = await enqueue(db, session, RunKind.GENERATE.value, {
            "idea": body.idea.strip(), "plan": body.plan, "groups": body.groups or body.plan is not None,
        })
    return {"polygon_id": polygon_id, "name": body.name, "session": session_out(session), "run": run_out(run)}


@router.get("/problems/{polygon_id}/session")
async def route_open_session(
    polygon_id: int,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """The problem's session (created on first open) with the chat history."""
    session = await _get_or_create(db, user_id, polygon_id)
    session.last_opened_at = utcnow()
    await db.commit()
    messages = (await db.execute(
        select(Message).where(Message.session_id == session.id).order_by(Message.id.desc()).limit(MESSAGE_PAGE)
    )).scalars().all()
    events = (await db.execute(
        select(Event).where(Event.session_id == session.id, Event.seen.is_(False)).order_by(Event.id)
    )).scalars().all()
    last_event = await db.scalar(
        select(Event.id).where(Event.session_id == session.id).order_by(Event.id.desc()).limit(1)
    )
    return {
        **session_out(session),
        "messages": [message_out(m) for m in reversed(messages)],
        "unseen_events": [event_out(e) for e in events],
        "last_event_id": last_event or 0,
        "active_run": run_out(await _active_run(db, session.id)),
        "latest_build": build_out(await _latest_build(db, session.id)),
    }


@router.patch("/sessions/{session_id}")
async def route_patch_session(
    session_id: str,
    body: SessionPatch,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    session = await _session(db, session_id, user_id)
    if body.model is not None:
        session.model = normalize_model(body.model)
    if body.problem_type is not None:
        session.problem_type = body.problem_type
    if body.auto_build is not None:
        session.settings = {**(session.settings or {}), "auto_build": body.auto_build}
    await db.commit()
    return session_out(session)


@router.post("/sessions/{session_id}/sync")
async def route_sync(
    session_id: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    client_factory: Callable[[int], PolygonClient] = Depends(get_client_factory),
) -> dict:
    """Re-read the problem from Polygon; changes made elsewhere become a notification."""
    session = await _session(db, session_id, user_id)
    if await has_active_run(db, session.id):
        return {"skipped": True, "reason": "идёт операция ИИ", "event": None}
    try:
        _, event = await sync_session(db, session, client_factory(user_id), announce=True)
    except SnapshotError as e:
        raise HTTPException(status_code=502, detail=f"Не удалось прочитать задачу из Polygon: {e}")
    return {
        "skipped": False,
        "event": event_out(event) if event else None,
        "last_synced_at": session.last_synced_at.isoformat() if session.last_synced_at else None,
        "sync_error": session.sync_error,
    }


@router.get("/sessions/{session_id}/state")
async def route_state(
    session_id: str,
    after_message: int = 0,
    after_event: int = 0,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """What changed since the given message/event ids (the UI polls this)."""
    session = await _session(db, session_id, user_id)
    messages = (await db.execute(
        select(Message).where(Message.session_id == session.id, Message.id > after_message)
        .order_by(Message.id).limit(MESSAGE_PAGE)
    )).scalars().all()
    events = (await db.execute(
        select(Event).where(Event.session_id == session.id, Event.id > after_event).order_by(Event.id).limit(100)
    )).scalars().all()
    return {
        "messages": [message_out(m) for m in messages],
        "events": [event_out(e) for e in events],
        "active_run": run_out(await _active_run(db, session.id)),
        "latest_build": build_out(await _latest_build(db, session.id)),
        "last_synced_at": session.last_synced_at.isoformat() if session.last_synced_at else None,
        "sync_error": session.sync_error,
    }


@router.post("/sessions/{session_id}/events/seen")
async def route_events_seen(
    session_id: str,
    body: EventsSeenIn,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    session = await _session(db, session_id, user_id)
    await db.execute(
        update(Event).where(Event.session_id == session.id, Event.id <= body.up_to).values(seen=True)
    )
    await db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- runs
@router.post("/sessions/{session_id}/messages")
async def route_post_message(
    session_id: str,
    body: MessageIn,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Store the user's message and queue its processing."""
    session = await _session(db, session_id, user_id)
    context = body.context.model_dump(exclude_none=True) if body.context else {}
    message = Message(session_id=session.id, role="user", content=body.text.strip(), meta={"context": context})
    db.add(message)
    await db.commit()
    run = await enqueue(db, session, RunKind.CHAT.value, {"message_id": message.id, "context": context})
    message.meta = {**message.meta, "run_id": run.id}
    await db.commit()
    return {"message": message_out(message), "run": run_out(run)}


@router.post("/sessions/{session_id}/generate")
async def route_generate(
    session_id: str,
    body: GenerateIn,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    session = await _session(db, session_id, user_id)
    if body.plan is not None:
        _plan_or_422(body.plan)
    db.add(Message(session_id=session.id, role="user", content=body.idea.strip(), meta={"intent": "generate"}))
    await db.commit()
    run = await enqueue(db, session, RunKind.GENERATE.value, body.model_dump())
    return {"run": run_out(run)}


@router.get("/sessions/{session_id}/plan")
async def route_get_plan(
    session_id: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """The saved plan, or a draft reconstructed from the groups on Polygon."""
    session = await _session(db, session_id, user_id)
    saved = (session.settings or {}).get("groups_plan")
    if saved:
        return {"plan": saved, "source": "saved"}
    snapshot = await load_snapshot(db, session.id) or {}
    draft = plan_from_snapshot(snapshot)
    return {"plan": draft, "source": "polygon" if draft else "empty"}


@router.post("/sessions/{session_id}/plan/preview")
async def route_preview_plan(
    session_id: str,
    body: PlanIn,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Validate a plan and show what it becomes: the script and the scoring table."""
    await _session(db, session_id, user_id)
    plan = _plan_or_422(body.plan)
    return {
        "plan": plan.to_dict(),
        "script": build_script(plan),
        "scoring": scoring_section(plan),
        "tests": len(expand_lines(plan)),
        "total_points": plan.total_points,
    }


@router.post("/sessions/{session_id}/groups")
async def route_groups(
    session_id: str,
    body: GroupsIn,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    session = await _session(db, session_id, user_id)
    if body.plan is None and not (body.request or "").strip():
        raise HTTPException(status_code=422, detail="Нужен план или описание групп")
    if body.plan is not None:
        _plan_or_422(body.plan)
    text = (body.request or "").strip() or "Применить план групп из редактора"
    db.add(Message(session_id=session.id, role="user", content=text, meta={"intent": "groups"}))
    await db.commit()
    run = await enqueue(db, session, RunKind.GROUPS.value, body.model_dump())
    return {"run": run_out(run)}


@router.post("/sessions/{session_id}/build")
async def route_build(
    session_id: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Build the package; a failed build is repaired automatically (up to 3 times)."""
    session = await _session(db, session_id, user_id)
    queued = (await db.execute(
        select(Run).where(Run.session_id == session.id, Run.kind == RunKind.BUILD.value,
                          Run.status.in_(ACTIVE_RUN_STATUSES))
    )).scalars().first()
    if queued is not None:
        return {"run": run_out(queued), "already": True}
    run = await enqueue(db, session, RunKind.BUILD.value, {"reason": "user"})
    return {"run": run_out(run), "already": False}


@router.get("/sessions/{session_id}/builds")
async def route_builds(
    session_id: str,
    limit: int = 20,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict | None]:
    session = await _session(db, session_id, user_id)
    rows = (await db.execute(
        select(Build).where(Build.session_id == session.id).order_by(Build.id.desc()).limit(min(limit, 100))
    )).scalars().all()
    return [build_out(b) for b in rows]


@router.get("/runs/{run_id}")
async def route_get_run(
    run_id: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict | None:
    run = await db.get(Run, run_id)
    if run is None or run.user_id != user_id:
        raise HTTPException(status_code=404, detail="Операция не найдена")
    return run_out(run)


@router.post("/runs/{run_id}/cancel")
async def route_cancel_run(
    run_id: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict | None:
    run = await db.get(Run, run_id)
    if run is None or run.user_id != user_id:
        raise HTTPException(status_code=404, detail="Операция не найдена")
    # only a still-queued run is cancelled outright; the worker may claim it any moment
    cancelled = await db.execute(
        update(Run)
        .where(Run.id == run_id, Run.status == RunStatus.QUEUED.value)
        .values(status=RunStatus.CANCELLED.value, finished_at=utcnow(), step="Отменено")
    )
    if not cancelled.rowcount:  # type: ignore[attr-defined]
        await db.execute(
            update(Run).where(Run.id == run_id, Run.status == RunStatus.RUNNING.value).values(cancel_requested=True)
        )
    await db.commit()
    await db.refresh(run)
    return run_out(run)


# --------------------------------------------------------------------------- assists
@router.post("/sessions/{session_id}/scoring")
async def route_scoring(
    session_id: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """The «Система оценки» table for the current plan (no model call)."""
    session = await _session(db, session_id, user_id)
    raw = (session.settings or {}).get("groups_plan") or plan_from_snapshot(await load_snapshot(db, session.id) or {})
    if not raw:
        raise HTTPException(status_code=409, detail="Сначала задайте группы тестов")
    plan = _plan_or_422(raw)
    return {"scoring": scoring_section(plan)}


@router.post("/sessions/{session_id}/solution-draft")
async def route_solution_draft(
    session_id: str,
    body: SolutionDraftIn,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    llm: LLM = Depends(get_llm),
    client_factory: Callable[[int], PolygonClient] = Depends(get_client_factory),
) -> dict:
    """A solution with the given tag for the «add file» form (not saved anywhere)."""
    session = await _session(db, session_id, user_id)
    snapshot = await load_snapshot(db, session.id)
    if snapshot is None:
        try:
            snapshot, _ = await sync_session(db, session, client_factory(user_id), announce=False)
        except SnapshotError as e:
            raise HTTPException(status_code=502, detail=str(e))
    dossier = build_dossier(snapshot, polygon_id=session.polygon_id, problem_type=session.problem_type)
    try:
        return await assist.solution_draft(
            llm, normalize_model(session.model), dossier,
            tag=body.tag.upper(), name=body.name, instruction=body.instruction,
        )
    except LLMError as e:
        raise HTTPException(status_code=502, detail=e.message)


@router.post("/assist/checker-validator")
async def route_checker_validator(
    body: CheckerValidatorIn,
    user_id: int = Depends(get_current_user),
    llm: LLM = Depends(get_llm),
) -> dict:
    """Checker + validator for a statement (used by the backend's archive import)."""
    try:
        return await assist.checker_validator(llm, normalize_model(body.model), body.statement.model_dump())
    except LLMError as e:
        raise HTTPException(status_code=502, detail=e.message)
