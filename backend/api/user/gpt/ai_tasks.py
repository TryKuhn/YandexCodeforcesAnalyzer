# api/user/gpt/router.py

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any

from fastapi import BackgroundTasks, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.database import get_db
from models.ai.ai_generated_file import AIGeneratedFile
from models.ai.ai_session import AISession, PipelineStage

from api.crypt import get_current_user
from api.user.gpt import gpt_router
from api.user.gpt.services.ai_file_helpers import (get_all_file_contents,
                                                   get_session_files,
                                                   upsert_ai_file,
                                                   upsert_all_ai_files)
from api.user.gpt.services.ai_service import TaskAIService
from api.user.gpt.services.upload_orchestrator import (
    retry_upload_after_manual_fix, run_upload_pipeline)
from api.pydantic_schemas.user.ai_task import (AddCustomSolutionRequest,
                                               AIStatementRequest,
                                               AIStatementResponse,
                                               ApproveFilesRequest,
                                               ApproveStatementRequest,
                                               ChatRequest,
                                               GenerateSamplesRequest,
                                               GenerateScoringRequest,
                                               ImportFromPolygonFullRequest,
                                               ImportFromPolygonRequest,
                                               ManualFixRequest,
                                               PostBuildRefineRequest,
                                               RefineFileRequest,
                                               RefineRequest,
                                               SuggestTagsRequest,
                                               UpdateExamplesRequest,
                                               UpdateProblemSettingsRequest,
                                               UpdateSessionSettingsRequest,
                                               UpdateStatementFieldRequest)

logger = logging.getLogger(__name__)


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def touch(session: AISession) -> None:
    session.updated_at = now_utc()


def _reconstruct_chat_log_from_history(history: list) -> list:
    """Build a human-readable chat_log from raw LLM history for legacy sessions."""
    entries = []
    for i, msg in enumerate(history or []):
        role = msg.get("role", "")
        if role == "system":
            continue
        content = msg.get("content", "") or ""
        # If assistant message looks like a statement JSON, show a summary
        if role == "assistant" and content.lstrip().startswith("{"):
            try:
                data = json.loads(content)
                if isinstance(data, dict) and "name" in data:
                    content = f"Условие обновлено: «{data['name']}»"
                elif isinstance(data, dict):
                    content = "Ответ получен (JSON)"
            except (json.JSONDecodeError, TypeError):
                pass
        entries.append(
            {
                "id": f"hist-{i}",
                "role": role,
                "content": content[:3000],
                "timestamp": "",
            }
        )
    return entries


async def get_session_or_404(
    session_id: str,
    user_id: int,
    db: AsyncSession,
) -> AISession:
    session = await db.get(AISession, session_id)
    if not session:
        raise HTTPException(404, "Сессия не найдена")
    if session.user_id != user_id:
        raise HTTPException(403, "Нет доступа")
    return session


# ─────────────────────────── Список сессий ──────────────────────────────────


@gpt_router.get("/sessions")
async def list_sessions(
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(AISession)
        .where(AISession.user_id == user_id)
        .order_by(AISession.updated_at.desc())
    )
    sessions = result.scalars().all()

    return [
        {
            "session_id": s.id,
            "stage": s.stage,
            "name": (
                s.statement.get("name", "Без названия") if s.statement else "Черновик"
            ),
            "model": s.model,
            "polygon_problem_id": s.polygon_problem_id,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "updated_at": s.updated_at.isoformat() if s.updated_at else None,
        }
        for s in sessions
    ]


# ─────────────────────── Создание сессии ────────────────────────────────────


@gpt_router.post("/create-session")
async def create_session(
    request: AIStatementRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    ts = now_utc()
    idea = (request.idea or "").strip()

    default_settings = {
        "input_file": "stdin",
        "output_file": "stdout",
        "interactive": False,
        "time_limit": 2000,
        "memory_limit": 256,
        "tags": [],
        "enable_groups": False,
        "enable_points": False,
    }

    if not idea:
        session = AISession(
            id=str(uuid.uuid4()),
            user_id=user_id,
            model=request.model,
            system_prompt=request.user_prompt or "",
            statement=None,
            history=[],
            stage=PipelineStage.STATEMENT,
            progress={"status": "idle"},
            problem_settings=default_settings,
            solution_meta={},
            examples=[],
            created_at=ts,
            updated_at=ts,
        )
        db.add(session)
        await db.commit()
        return {
            "session_id": session.id,
            "statement": None,
            "stage": PipelineStage.STATEMENT,
        }

    try:
        ai = TaskAIService()
        statement_data = await ai.generate_statement(
            user_idea=idea,
            model=request.model,
            user_prompt=request.user_prompt or "",
            history=request.history or [],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка генерации условия: {e}")

    session = AISession(
        id=str(uuid.uuid4()),
        user_id=user_id,
        model=request.model,
        system_prompt=request.user_prompt or "",
        statement=statement_data,
        history=request.history or [],
        stage=PipelineStage.STATEMENT,
        progress={"status": "idle"},
        problem_settings=default_settings,
        solution_meta={},
        examples=[],
        created_at=ts,
        updated_at=ts,
    )
    db.add(session)
    await db.commit()

    return AIStatementResponse(
        statement=statement_data,
        session_id=session.id,
        stage=PipelineStage.STATEMENT,
    )


# ─────────────────────── Удаление сессии ────────────────────────────────────


@gpt_router.delete("/session/{session_id}")
async def delete_session(
    session_id: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await get_session_or_404(session_id, user_id, db)
    await db.execute(
        delete(AIGeneratedFile).where(AIGeneratedFile.session_id == session_id)
    )
    await db.delete(session)
    await db.commit()
    return {"status": "deleted"}


# ─────────────────────────── ЭТАП 1: Условие ────────────────────────────────


@gpt_router.post("/refine-statement", response_model=AIStatementResponse)
async def refine_statement(
    request: RefineRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await get_session_or_404(request.session_id, user_id, db)

    if session.stage not in (PipelineStage.STATEMENT, PipelineStage.FILES_REVIEW):
        raise HTTPException(
            400, f"Нельзя редактировать условие на этапе '{session.stage}'"
        )

    # Persist settings from frontend if provided (safety net for unsaved UI state)
    if request.problem_settings:
        session.problem_settings = {
            **(session.problem_settings or {}),
            **request.problem_settings,
        }
        flag_modified(session, "problem_settings")

    problem_settings = request.problem_settings or session.problem_settings or {}

    history = list(session.history or [])
    if session.statement:
        history.append(
            {
                "role": "assistant",
                "content": json.dumps(session.statement, ensure_ascii=False),
            }
        )
    history.append({"role": "user", "content": request.feedback})

    ai = TaskAIService()
    new_statement = await ai.generate_statement(
        user_idea=request.feedback,
        model=session.model,
        user_prompt=session.system_prompt,
        history=history,
    )

    stmt = dict(new_statement)

    # Preserve / regenerate interaction for interactive problems
    if problem_settings.get("interactive"):
        prev_interaction = (session.statement or {}).get("interaction")
        if prev_interaction:
            stmt["interaction"] = prev_interaction
        else:
            stmt["interaction"] = await ai.generate_interaction_text(
                stmt, session.model
            )

    # Preserve / regenerate scoring when groups or points are enabled
    if problem_settings.get("enable_groups") or problem_settings.get("enable_points"):
        prev_scoring = (session.statement or {}).get("scoring")
        if prev_scoring:
            stmt["scoring"] = prev_scoring
        else:
            stmt["scoring"] = await ai.generate_scoring(
                stmt,
                session.model,
                enable_groups=bool(problem_settings.get("enable_groups")),
                enable_points=bool(problem_settings.get("enable_points")),
            )

    session.history = history
    session.statement = stmt
    flag_modified(session, "statement")
    touch(session)
    await db.commit()

    tech_data = None
    if session.stage == PipelineStage.FILES_REVIEW:
        try:
            ai_regen = TaskAIService()
            tech_data = await ai_regen.generate_technical_stuff(stmt, session.model)
            if problem_settings.get("interactive"):
                interactor_code = await ai_regen.generate_interactor(
                    stmt, session.model
                )
                tech_data["interactor"] = interactor_code
            await upsert_all_ai_files(db, session.id, tech_data, uploaded=False)
            touch(session)
            await db.commit()
        except Exception as e:
            logger.warning(f"Failed to regenerate files after statement refine: {e}")
            tech_data = None

    response_data = {
        "statement": stmt,
        "session_id": session.id,
        "stage": session.stage,
    }
    if tech_data:
        response_data["technical_data"] = tech_data
    return response_data


@gpt_router.post("/approve-statement")
async def approve_statement(
    request: ApproveStatementRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await get_session_or_404(request.session_id, user_id, db)

    if session.stage not in (PipelineStage.STATEMENT, PipelineStage.FAILED):
        raise HTTPException(400, f"Нельзя одобрить условие на этапе '{session.stage}'")

    session.stage = PipelineStage.FILES_REVIEW
    session.progress = {
        "status": "generating_files",
        "current_step": "Генерация технических файлов...",
    }
    touch(session)
    await db.commit()

    try:
        ai = TaskAIService()
        tech_data = await ai.generate_technical_stuff(session.statement, session.model)

        problem_settings = request.problem_settings or session.problem_settings or {}
        stmt = dict(session.statement or {})
        stmt_changed = False

        if request.problem_settings:
            merged = {**(session.problem_settings or {}), **request.problem_settings}
            session.problem_settings = merged
            flag_modified(session, "problem_settings")

        if problem_settings.get("interactive"):
            interactor_code = await ai.generate_interactor(stmt, session.model)
            tech_data["interactor"] = interactor_code

            if not stmt.get("interaction"):
                interaction_text = await ai.generate_interaction_text(
                    stmt, session.model
                )
                stmt["interaction"] = interaction_text
                stmt_changed = True

        if problem_settings.get("enable_groups") or problem_settings.get(
            "enable_points"
        ):
            if not stmt.get("scoring"):
                scoring_text = await ai.generate_scoring(
                    stmt,
                    session.model,
                    enable_groups=bool(problem_settings.get("enable_groups")),
                    enable_points=bool(problem_settings.get("enable_points")),
                )
                stmt["scoring"] = scoring_text
                stmt_changed = True

        if stmt_changed:
            session.statement = stmt
            flag_modified(session, "statement")

        await upsert_all_ai_files(db, session.id, tech_data, uploaded=False)

        session.progress = {
            "status": "files_ready",
            "current_step": "Файлы готовы к проверке",
        }
        touch(session)
        await db.commit()
        await db.refresh(session)

        generated_sections = []
        if stmt.get("interaction"):
            generated_sections.append("Взаимодействие")
        if stmt.get("scoring"):
            generated_sections.append("Система оценки")

        return {
            "session_id": session.id,
            "stage": session.stage,
            "technical_data": tech_data,
            "statement": session.statement,
            "generated_sections": generated_sections,
        }

    except Exception as e:
        session.stage = PipelineStage.FAILED
        session.progress = {
            "status": "failed",
            "error": str(e),
            "current_step": "Ошибка генерации файлов",
        }
        touch(session)
        await db.commit()
        raise HTTPException(500, f"Ошибка генерации файлов: {e}")


@gpt_router.post("/refine-file")
async def refine_file(
    request: RefineFileRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await get_session_or_404(request.session_id, user_id, db)

    session_files = await get_session_files(db, session.id)
    file_obj = session_files.get(request.file_key)
    if file_obj is None:
        raise HTTPException(400, f"Файл '{request.file_key}' не найден в сессии")

    ai = TaskAIService()
    new_code = await ai.refine_file(
        file_key=request.file_key,
        current_code=file_obj.content,
        feedback=request.feedback,
        statement=session.statement,
        model=session.model,
    )

    await upsert_ai_file(db, session.id, request.file_key, new_code, uploaded=False)
    touch(session)
    await db.commit()

    return {
        "session_id": session.id,
        "file_key": request.file_key,
        "new_code": new_code,
        "stage": session.stage,
    }


@gpt_router.post("/manual-fix-file")
async def manual_fix_file(
    request: ManualFixRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Пользователь вручную правит файл — сохраняем на сервере"""
    session = await get_session_or_404(request.session_id, user_id, db)

    await upsert_ai_file(
        db, session.id, request.file_key, request.new_content, uploaded=False
    )

    upload_errors = dict(session.upload_errors or {})
    upload_errors.pop(request.file_key, None)
    session.upload_errors = upload_errors

    touch(session)
    await db.commit()

    return {
        "session_id": session.id,
        "file_key": request.file_key,
        "stage": session.stage,
        "remaining_errors": list(upload_errors.keys()),
    }


@gpt_router.post("/approve-files")
async def approve_files(
    request: ApproveFilesRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Пользователь одобряет файлы → запускаем загрузку в Polygon"""
    session = await get_session_or_404(request.session_id, user_id, db)

    if session.stage not in (
        PipelineStage.FILES_REVIEW,
        PipelineStage.FAILED,
        PipelineStage.FIXING_ERRORS,
    ):
        raise HTTPException(
            400, f"Нельзя запустить загрузку на этапе '{session.stage}'"
        )

    session_files = await get_session_files(db, session.id)
    if not session_files:
        raise HTTPException(400, "Нет технических файлов для загрузки")

    session.stage = PipelineStage.UPLOADING
    session.progress = {
        "status": "uploading",
        "current_step": "Запуск загрузки в Polygon...",
    }
    touch(session)
    await db.commit()

    background_tasks.add_task(run_upload_pipeline, request.session_id)
    return {"status": "upload_started", "session_id": request.session_id}


@gpt_router.post("/retry-after-manual-fix")
async def retry_after_manual_fix_endpoint(
    request: ApproveFilesRequest,
    background_tasks: BackgroundTasks,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    После ручных правок (или доработки из стадии DONE) — повторяем загрузку
    только изменённых файлов на Polygon.
    """
    session = await get_session_or_404(request.session_id, user_id, db)

    if session.stage not in (
        PipelineStage.FIXING_ERRORS,
        PipelineStage.FAILED,
        PipelineStage.DONE,
    ):
        raise HTTPException(
            400, f"Повтор загрузки недоступен на этапе '{session.stage}'"
        )

    session.stage = PipelineStage.UPLOADING
    session.progress = {
        "status": "uploading",
        "current_step": "Повторная загрузка в Polygon...",
    }
    session.upload_errors = {}
    touch(session)
    await db.commit()

    background_tasks.add_task(retry_upload_after_manual_fix, request.session_id)
    return {"status": "retry_started", "session_id": request.session_id}


# ──────────────────────────── Прогресс ──────────────────────────────────────


@gpt_router.get("/upload-progress/{session_id}")
async def get_upload_progress(
    session_id: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await get_session_or_404(session_id, user_id, db)
    progress = session.progress or {}

    return {
        "status": progress.get("status", "idle"),
        "stage": session.stage,
        "current_step": progress.get("current_step"),
        "error": progress.get("error"),
        "retries": progress.get("retries"),
        "upload_errors": session.upload_errors or {},
        "polygon_problem_id": session.polygon_problem_id,
        "technical_data": await get_all_file_contents(db, session_id),
        "problem_settings": session.problem_settings or {},
        "solution_meta": session.solution_meta or {},
        "examples": session.examples or [],
    }


# ──────────────── Получение сессии (загрузка страницы) ──────────────────────


@gpt_router.get("/session/{session_id}")
async def get_session(
    session_id: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await get_session_or_404(session_id, user_id, db)

    chat_log = session.chat_log or []
    if not chat_log and session.history:
        chat_log = _reconstruct_chat_log_from_history(session.history)

    return {
        "session_id": session.id,
        "stage": session.stage,
        "statement": session.statement,
        "technical_data": await get_all_file_contents(db, session_id),
        "history": session.history or [],
        "chat_log": chat_log,
        "model": session.model,
        "system_prompt": session.system_prompt,
        "progress": session.progress or {"status": "idle"},
        "upload_errors": session.upload_errors or {},
        "polygon_problem_id": session.polygon_problem_id,
        "problem_settings": session.problem_settings or {},
        "solution_meta": session.solution_meta or {},
        "examples": session.examples or [],
    }


# ──────────────── Обновление настроек сессии ────────────────────────────────


@gpt_router.patch("/session/{session_id}/settings")
async def update_session_settings(
    session_id: str,
    request: UpdateSessionSettingsRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await get_session_or_404(session_id, user_id, db)

    if request.model is not None:
        session.model = request.model
    if request.system_prompt is not None:
        session.system_prompt = request.system_prompt

    touch(session)
    await db.commit()
    return {
        "status": "ok",
        "model": session.model,
        "system_prompt": session.system_prompt,
    }


# ──────────────── Импорт из Polygon ─────────────────────────────────────────


@gpt_router.post("/import-from-polygon")
async def import_from_polygon(
    request: ImportFromPolygonRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Создаёт AI-сессию с условием существующей задачи из Polygon (только условие)."""
    from api.user.polygon.get_problem_statement import get_problem_statement

    statement = await get_problem_statement(request.polygon_problem_id, user_id, db)

    ts = now_utc()
    session = AISession(
        id=str(uuid.uuid4()),
        user_id=user_id,
        model=request.model,
        system_prompt="",
        statement=statement,
        history=[],
        stage=PipelineStage.STATEMENT,
        progress={"status": "idle"},
        polygon_problem_id=request.polygon_problem_id,
        created_at=ts,
        updated_at=ts,
    )
    db.add(session)
    await db.commit()

    return {
        "session_id": session.id,
        "statement": statement,
        "stage": PipelineStage.STATEMENT,
        "polygon_problem_id": request.polygon_problem_id,
    }


@gpt_router.post("/import-from-polygon-full")
async def import_from_polygon_full(
    request: ImportFromPolygonFullRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Создаёт AI-сессию, загружая условие, файлы, настройки и теги из Polygon."""
    from api.user.polygon.get_problem_files import (get_problem_files,
                                                    get_problem_script,
                                                    get_problem_solutions,
                                                    get_problem_tags,
                                                    get_problem_tests,
                                                    get_test_input, view_file,
                                                    view_solution)
    from api.user.polygon.get_problem_statement import get_problem_statement
    from api.user.polygon.problem_info import problem_info as get_problem_info

    problem_id = request.polygon_problem_id

    statement = await get_problem_statement(problem_id, user_id, db)

    # Problem info (TL, ML, interactive, etc.)
    try:
        info = await get_problem_info(problem_id, user_id, db)
    except Exception:
        info = {}

    problem_settings: Dict[str, Any] = {
        "input_file": info.get("inputFile", "stdin") or "stdin",
        "output_file": info.get("outputFile", "stdout") or "stdout",
        "interactive": bool(info.get("interactive", False)),
        "time_limit": info.get("timeLimit", 2000) or 2000,
        "memory_limit": info.get("memoryLimit", 256) or 256,
        "tags": [],
        "enable_groups": False,
        "enable_points": False,
    }

    # Tags
    try:
        tags = await get_problem_tags(problem_id, user_id, db)
        problem_settings["tags"] = tags
    except Exception:
        pass

    ts = now_utc()
    session = AISession(
        id=str(uuid.uuid4()),
        user_id=user_id,
        model=request.model,
        system_prompt="",
        statement=statement,
        history=[],
        stage=PipelineStage.STATEMENT,
        progress={"status": "idle"},
        polygon_problem_id=problem_id,
        problem_settings=problem_settings,
        solution_meta={},
        examples=[],
        created_at=ts,
        updated_at=ts,
    )
    db.add(session)
    await db.flush()

    tech_data = {}

    if request.load_files:
        # Load source files (validator, checker, generator, interactor)
        KNOWN_SOURCE_FILES = {
            "validator.cpp": "validator",
            "checker.cpp": "checker",
            "generator.cpp": "generator",
            "interactor.cpp": "interactor",
        }
        try:
            files_info = await get_problem_files(problem_id, user_id, db)
            source_files = files_info.get("sourceFiles", []) or []
            for f in source_files:
                name = f.get("name", "")
                if name in KNOWN_SOURCE_FILES:
                    try:
                        content = await view_file(
                            problem_id, "source", name, user_id, db
                        )
                        file_type = KNOWN_SOURCE_FILES[name]
                        tech_data[file_type] = content
                        await upsert_ai_file(
                            db, session.id, file_type, content, uploaded=True
                        )
                    except Exception as e:
                        logger.warning(f"Failed to load file {name}: {e}")
        except Exception as e:
            logger.warning(f"Failed to load problem files: {e}")

        try:
            solutions = await get_problem_solutions(problem_id, user_id, db)
            solution_meta = {}
            for sol in solutions:
                name = sol.get("name", "")
                tag = sol.get("tag", "OK")
                try:
                    content = await view_solution(problem_id, name, user_id, db)
                    if tag == "MA":
                        file_type = "solution_cpp"
                    elif tag in ("WA", "wa"):
                        file_type = "wa_sol"
                    elif tag in ("TL", "tl"):
                        file_type = "tl_sol"
                    elif tag in ("ML", "ml"):
                        file_type = "ml_sol"
                    elif tag in ("RE", "re"):
                        file_type = "re_sol"
                    else:
                        # Custom solution
                        file_type = f"sol_custom_{uuid.uuid4().hex[:8]}"
                        solution_meta[file_type] = {"tag": tag, "name": name}
                    tech_data[file_type] = content
                    await upsert_ai_file(
                        db, session.id, file_type, content, uploaded=True
                    )
                except Exception as e:
                    logger.warning(f"Failed to load solution {name}: {e}")
            if solution_meta:
                session.solution_meta = solution_meta
        except Exception as e:
            logger.warning(f"Failed to load solutions: {e}")

        # Load script
        try:
            script = await get_problem_script(problem_id, "tests", user_id, db)
            if script:
                tech_data["script"] = script
                await upsert_ai_file(db, session.id, "script", script, uploaded=True)
        except Exception:
            pass

        # Load example tests
        try:
            tests = await get_problem_tests(problem_id, "tests", user_id, db)
            examples = []
            for t in tests:
                if t.get("useInStatements"):
                    idx = t.get("index", 0)
                    try:
                        inp = await get_test_input(
                            problem_id, "tests", idx, user_id, db
                        )
                        examples.append({"index": idx, "input": inp, "output": ""})
                    except Exception:
                        pass
            if examples:
                session.examples = examples
        except Exception:
            pass

    await db.commit()

    return {
        "session_id": session.id,
        "statement": statement,
        "stage": PipelineStage.STATEMENT,
        "polygon_problem_id": problem_id,
        "problem_settings": problem_settings,
        "technical_data": tech_data,
        "examples": session.examples or [],
    }


# ──────────────── Пост-билд доработка ───────────────────────────────────────


# ────────────────────── Unified Chat (two-agent) ────────────────────────────


def _append_chat(session: AISession, *entries: dict) -> None:
    """Append one or more entries to session.chat_log."""
    log = list(session.chat_log or [])
    log.extend(entries)
    session.chat_log = log
    flag_modified(session, "chat_log")


_FILE_LABELS = {
    "validator": "validator.cpp",
    "generator": "generator.cpp",
    "checker": "checker.cpp",
    "interactor": "interactor.cpp",
    "solution_cpp": "solution.cpp",
    "solution_py": "solution.py",
    "wa_sol": "wa.cpp",
    "tl_sol": "tl.cpp",
    "re_sol": "re.cpp",
    "ml_sol": "ml.cpp",
    "script": "script.txt",
}


def _file_label(key: str) -> str:
    return _FILE_LABELS.get(key, key)


@gpt_router.post("/chat")
async def unified_chat(
    request: ChatRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Unified chat endpoint with two-agent architecture:
    - Router agent: classifies user intent as 'modify' or 'answer'
    - Executor agent: modifies files/statement OR answers the question
    Appends both user and assistant entries to session.chat_log.
    """
    session = await get_session_or_404(request.session_id, user_id, db)

    ai = TaskAIService()
    current_files = await get_all_file_contents(db, session.id)
    ts = now_utc().isoformat()

    # ── 1. Router agent ──────────────────────────────────────────────────────
    intent = await ai.classify_intent(
        message=request.message,
        context=request.context,
        model=session.model,
    )

    response_text = ""
    updated_files: list[str] = []
    new_statement = None
    new_tech_data = None

    # ── 2. Executor ──────────────────────────────────────────────────────────
    if intent == "modify":
        ctx = request.context

        if ctx == "statement":
            # Reuse statement-refine logic
            history = list(session.history or [])
            if session.statement:
                history.append(
                    {
                        "role": "assistant",
                        "content": json.dumps(session.statement, ensure_ascii=False),
                    }
                )
            history.append({"role": "user", "content": request.message})

            new_stmt = await ai.generate_statement(
                user_idea=request.message,
                model=session.model,
                user_prompt=session.system_prompt,
                history=history,
            )
            session.history = history
            session.statement = new_stmt
            flag_modified(session, "statement")
            new_statement = new_stmt
            response_text = "✏️ Обновил условие задачи."

        elif ctx == "task":
            # Reuse post-build-refine logic
            if not current_files:
                response_text = "❌ Нет файлов для обновления."
            else:
                updated = await ai.post_build_refine(
                    message=request.message,
                    statement=session.statement,
                    current_files=current_files,
                    model=session.model,
                )
                for file_key, content in updated.items():
                    await upsert_ai_file(
                        db, session.id, file_key, content, uploaded=False
                    )
                updated_files = list(updated.keys())
                new_tech_data = await get_all_file_contents(db, session.id)
                if updated_files:
                    labels = ", ".join(_file_label(k) for k in updated_files)
                    response_text = f"✅ Обновлено: {labels}."
                else:
                    response_text = "🤔 Не нашёл, что изменить. Уточните запрос."

        else:
            # Specific file refine
            file_obj = (await get_session_files(db, session.id)).get(ctx)
            if file_obj is None:
                response_text = f"❌ Файл '{ctx}' не найден."
                intent = "answer"
            else:
                new_code = await ai.refine_file(
                    file_key=ctx,
                    current_code=file_obj.content,
                    feedback=request.message,
                    statement=session.statement,
                    model=session.model,
                )
                await upsert_ai_file(db, session.id, ctx, new_code, uploaded=False)
                updated_files = [ctx]
                new_tech_data = {ctx: new_code}
                response_text = f"✅ {_file_label(ctx)} обновлён."

    else:
        # Answer intent
        response_text = await ai.answer_question(
            message=request.message,
            context=request.context,
            statement=session.statement or {},
            files=current_files,
            model=session.model,
            history=list(session.history or []),
        )

    # ── 3. Append to chat_log ────────────────────────────────────────────────
    _append_chat(
        session,
        {
            "id": str(uuid.uuid4()),
            "role": "user",
            "content": request.message,
            "timestamp": ts,
            "context": request.context,
        },
        {
            "id": str(uuid.uuid4()),
            "role": "assistant",
            "content": response_text,
            "timestamp": ts,
            "context": request.context,
            "action": "modify_" + request.context if intent == "modify" else "answer",
            "updated_files": updated_files,
        },
    )

    touch(session)
    await db.commit()

    return {
        "action": intent,
        "response": response_text,
        "updated_files": updated_files,
        "statement": new_statement,
        "technical_data": new_tech_data,
    }


@gpt_router.post("/suggest-tags")
async def suggest_tags(
    request: SuggestTagsRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """ИИ предлагает теги для задачи на основе условия."""
    session = await get_session_or_404(request.session_id, user_id, db)
    if not session.statement:
        raise HTTPException(400, "Условие ещё не создано")

    ai = TaskAIService()
    tags = await ai.suggest_tags(session.statement, session.model)

    return {"session_id": session.id, "suggested_tags": tags}


@gpt_router.post("/generate-scoring")
async def generate_scoring(
    request: GenerateScoringRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """ИИ генерирует раздел Scoring для задачи с группами тестов/баллами."""
    session = await get_session_or_404(request.session_id, user_id, db)
    if not session.statement:
        raise HTTPException(400, "Условие ещё не создано")

    settings = session.problem_settings or {}
    enable_groups = settings.get("enable_groups", False)
    enable_points = settings.get("enable_points", False)

    if not enable_groups and not enable_points:
        raise HTTPException(400, "Включите группы тестов или баллы в настройках задачи")

    ai = TaskAIService()
    scoring_text = await ai.generate_scoring(
        session.statement, session.model, enable_groups, enable_points
    )

    stmt = dict(session.statement)
    stmt["scoring"] = scoring_text
    session.statement = stmt
    touch(session)
    await db.commit()

    return {"session_id": session.id, "scoring": scoring_text}


@gpt_router.patch("/session/{session_id}/statement-field")
async def update_statement_field(
    session_id: str,
    request: UpdateStatementFieldRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Обновляет отдельное поле в statement сессии (scoring, interaction, notes и тд)."""
    session = await get_session_or_404(session_id, user_id, db)
    if not session.statement:
        raise HTTPException(400, "Условие не создано")

    allowed_fields = {
        "scoring",
        "interaction",
        "notes",
        "tutorial",
        "legend",
        "input",
        "output",
        "name",
    }
    if request.field not in allowed_fields:
        raise HTTPException(
            400, f"Поле '{request.field}' не может быть изменено через этот эндпоинт"
        )

    stmt = dict(session.statement)
    stmt[request.field] = request.value
    session.statement = stmt
    touch(session)
    await db.commit()

    return {"session_id": session_id, "field": request.field, "value": request.value}


@gpt_router.post("/generate-samples")
async def generate_samples(
    request: GenerateSamplesRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """ИИ генерирует примеры тестов (сэмплы) для задачи."""
    session = await get_session_or_404(request.session_id, user_id, db)
    if not session.statement:
        raise HTTPException(400, "Условие ещё не создано")

    ai = TaskAIService()
    examples = await ai.generate_samples(
        session.statement, session.model, count=request.count or 3
    )

    indexed = [
        {"index": i + 1, "input": ex["input"], "output": ex["output"]}
        for i, ex in enumerate(examples)
    ]
    session.examples = indexed
    touch(session)
    await db.commit()

    return {"session_id": session.id, "examples": indexed}


@gpt_router.patch("/session/{session_id}/examples")
async def update_examples(
    session_id: str,
    request: UpdateExamplesRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Обновляет примеры тестов (сэмплы) в сессии."""
    session = await get_session_or_404(session_id, user_id, db)
    session.examples = list(request.examples)
    flag_modified(session, "examples")
    touch(session)
    await db.commit()
    return {"session_id": session_id, "examples": session.examples}


@gpt_router.patch("/session/{session_id}/problem-settings")
async def update_problem_settings(
    session_id: str,
    request: UpdateProblemSettingsRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Обновляет настройки задачи (TL, ML, interactive, файлы, теги и тд)."""
    session = await get_session_or_404(session_id, user_id, db)
    # Create a new dict — mutating in place won't be tracked by SQLAlchemy JSON columns
    session.problem_settings = {
        **(session.problem_settings or {}),
        **request.settings.model_dump(exclude_none=False),
    }
    flag_modified(session, "problem_settings")
    touch(session)
    await db.commit()
    return {"session_id": session_id, "problem_settings": session.problem_settings}


@gpt_router.post("/add-custom-solution")
async def add_custom_solution(
    request: AddCustomSolutionRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Добавляет новое пустое кастомное решение с заданным тегом и именем."""
    session = await get_session_or_404(request.session_id, user_id, db)

    file_type = f"sol_custom_{uuid.uuid4().hex[:8]}"
    name = request.name
    if not name.endswith(".cpp"):
        name += ".cpp"

    meta = dict(session.solution_meta or {})
    meta[file_type] = {"tag": request.tag, "name": name}
    session.solution_meta = meta

    await upsert_ai_file(
        db, session.id, file_type, "", uploaded=False, solution_meta=meta
    )
    touch(session)
    await db.commit()

    return {
        "session_id": session.id,
        "file_type": file_type,
        "name": name,
        "tag": request.tag,
        "solution_meta": meta,
    }


@gpt_router.delete("/session/{session_id}/solution/{file_type}")
async def delete_custom_solution(
    session_id: str,
    file_type: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Removes a custom solution from the session."""
    session = await get_session_or_404(session_id, user_id, db)

    if not file_type.startswith("sol_custom_"):
        raise HTTPException(400, "Можно удалять только кастомные решения")

    meta = dict(session.solution_meta or {})
    if file_type not in meta:
        raise HTTPException(404, f"Решение '{file_type}' не найдено")

    del meta[file_type]
    session.solution_meta = meta
    flag_modified(session, "solution_meta")

    await db.execute(
        delete(AIGeneratedFile)
        .where(AIGeneratedFile.session_id == session_id)
        .where(AIGeneratedFile.file_type == file_type)
    )

    touch(session)
    await db.commit()

    return {
        "session_id": session_id,
        "deleted": file_type,
        "solution_meta": meta,
    }


@gpt_router.post("/generate-solution")
async def generate_solution_for_custom(
    request: RefineFileRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """ИИ генерирует код для кастомного решения по промпту пользователя."""
    session = await get_session_or_404(request.session_id, user_id, db)
    if not session.statement:
        raise HTTPException(400, "Условие ещё не создано")

    solution_meta = session.solution_meta or {}
    meta = solution_meta.get(request.file_key)
    if not meta and request.file_key not in (
        "wa_sol",
        "tl_sol",
        "re_sol",
        "ml_sol",
        "solution_cpp",
        "solution_py",
    ):
        raise HTTPException(400, f"Файл '{request.file_key}' не найден")

    tag = meta["tag"] if meta else request.file_key.upper()
    name = meta.get("name", request.file_key) if meta else request.file_key

    ai = TaskAIService()
    code = await ai.generate_solution_for_tag(
        tag, name, session.statement, session.model
    )

    await upsert_ai_file(
        db,
        session.id,
        request.file_key,
        code,
        uploaded=False,
        solution_meta=solution_meta,
    )
    touch(session)
    await db.commit()

    return {
        "session_id": session.id,
        "file_key": request.file_key,
        "new_code": code,
    }


@gpt_router.post("/post-build-refine")
async def post_build_refine(
    request: PostBuildRefineRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Доработка задачи после успешной сборки — ИИ обновляет нужные файлы."""
    session = await get_session_or_404(request.session_id, user_id, db)

    if session.stage not in (
        PipelineStage.DONE,
        PipelineStage.FILES_REVIEW,
        PipelineStage.FIXING_ERRORS,
    ):
        raise HTTPException(400, f"Доработка недоступна на этапе '{session.stage}'")

    current_files = await get_all_file_contents(db, session.id)
    if not current_files:
        raise HTTPException(400, "Нет файлов для доработки")

    ai = TaskAIService()
    updated = await ai.post_build_refine(
        message=request.message,
        statement=session.statement,
        current_files=current_files,
        model=session.model,
    )

    for file_key, content in updated.items():
        await upsert_ai_file(db, session.id, file_key, content, uploaded=False)

    touch(session)
    await db.commit()

    return {
        "session_id": session.id,
        "updated_files": list(updated.keys()),
        "technical_data": await get_all_file_contents(db, session.id),
        "stage": session.stage,
    }
