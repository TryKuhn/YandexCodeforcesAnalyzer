# api/user/gpt/router.py

import json
import uuid
from datetime import datetime, timezone

from fastapi import BackgroundTasks, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import (AIStatementRequest,
                                               AIStatementResponse,
                                               ApproveFilesRequest,
                                               ApproveStatementRequest,
                                               ImportFromPolygonRequest,
                                               ManualFixRequest,
                                               PostBuildRefineRequest,
                                               RefineFileRequest,
                                               RefineRequest,
                                               UpdateSessionSettingsRequest)
from api.user.gpt import gpt_router
from api.user.gpt.services.ai_file_helpers import (get_all_file_contents,
                                                   get_session_files,
                                                   upsert_ai_file,
                                                   upsert_all_ai_files)
from api.user.gpt.services.ai_service import TaskAIService
from api.user.gpt.services.upload_orchestrator import (
    retry_upload_after_manual_fix, run_upload_pipeline)
from app.database import get_db
from models.ai.ai_generated_file import AIGeneratedFile
from models.ai.ai_session import AISession, PipelineStage

# ─────────────────── Вспомогательные функции ────────────────────────────────


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def touch(session: AISession) -> None:
    session.updated_at = now_utc()


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
            created_at=ts,
            updated_at=ts,
        )
        db.add(session)
        await db.commit()
        return {"session_id": session.id, "statement": None, "stage": PipelineStage.STATEMENT}

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
    await db.execute(delete(AIGeneratedFile).where(AIGeneratedFile.session_id == session_id))
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

    if session.stage != PipelineStage.STATEMENT:
        raise HTTPException(
            400, f"Нельзя редактировать условие на этапе '{session.stage}'"
        )

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

    session.history = history
    session.statement = new_statement
    touch(session)
    await db.commit()

    return AIStatementResponse(
        statement=new_statement,
        session_id=session.id,
        stage=PipelineStage.STATEMENT,
    )


# ─────────────────── ЭТАП 2: Одобрение условия ──────────────────────────────


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

        await upsert_all_ai_files(db, session.id, tech_data, uploaded=False)

        session.progress = {
            "status": "files_ready",
            "current_step": "Файлы готовы к проверке",
        }
        touch(session)
        await db.commit()

        return {
            "session_id": session.id,
            "stage": session.stage,
            "technical_data": tech_data,
            "technical_data": tech_data,
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


# ─────────────────── ЭТАП 3: Правка файлов ──────────────────────────────────


@gpt_router.post("/refine-file")
async def refine_file(
    request: RefineFileRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """ИИ правит конкретный файл по фидбеку пользователя"""
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

    await upsert_ai_file(db, session.id, request.file_key, request.new_content, uploaded=False)

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


# ─────────────────── ЭТАП 4: Одобрение файлов ───────────────────────────────


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


# ──────────────── ЭТАП 5: Повтор после ручного фикса / доработка ────────────


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
    }


# ──────────────── Получение сессии (загрузка страницы) ──────────────────────


@gpt_router.get("/session/{session_id}")
async def get_session(
    session_id: str,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    session = await get_session_or_404(session_id, user_id, db)

    return {
        "session_id": session.id,
        "stage": session.stage,
        "statement": session.statement,
        "technical_data": await get_all_file_contents(db, session_id),
        "history": session.history or [],
        "model": session.model,
        "system_prompt": session.system_prompt,
        "progress": session.progress or {"status": "idle"},
        "upload_errors": session.upload_errors or {},
        "polygon_problem_id": session.polygon_problem_id,
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
    return {"status": "ok", "model": session.model, "system_prompt": session.system_prompt}


# ──────────────── Импорт из Polygon ─────────────────────────────────────────


@gpt_router.post("/import-from-polygon")
async def import_from_polygon(
    request: ImportFromPolygonRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Создаёт AI-сессию с условием существующей задачи из Polygon."""
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


# ──────────────── Пост-билд доработка ───────────────────────────────────────


@gpt_router.post("/post-build-refine")
async def post_build_refine(
    request: PostBuildRefineRequest,
    user_id: int = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Доработка задачи после успешной сборки — ИИ обновляет нужные файлы."""
    session = await get_session_or_404(request.session_id, user_id, db)

    if session.stage not in (PipelineStage.DONE, PipelineStage.FILES_REVIEW, PipelineStage.FIXING_ERRORS):
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
