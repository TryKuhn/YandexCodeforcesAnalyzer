import json

from fastapi import Depends, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from api.user.gpt import gpt_router
from app.database import get_db
from api.crypt import get_current_user
from api.pydantic_schemas.user.ai_task import (
    AIStatementRequest, AIStatementResponse, RefineRequest,
    ApproveUploadRequest, UploadProgressResponse
)
from api.user.gpt.services.ai_service import TaskAIService
from api.user.gpt.services.session_store import SessionStore
from api.user.gpt.services.upload_orchestrator import run_upload_pipeline


@gpt_router.post("/generate-statement", response_model=AIStatementResponse)
async def generate_statement(
        request: AIStatementRequest,
        user_id: int = Depends(get_current_user)
):
    ai = TaskAIService()
    # ВАЖНО: вызываем специализированный метод
    statement_data = await ai.generate_statement(request.idea, request.history)

    session_id = SessionStore.create({
        "history": request.history or [],
        "last_statement": statement_data,
        "user_id": user_id
    })

    return AIStatementResponse(statement=statement_data, session_id=session_id)


@gpt_router.post("/refine-statement", response_model=AIStatementResponse)
async def refine_statement(
        request: RefineRequest,
        user_id: int = Depends(get_current_user)
):
    session = SessionStore.get(request.session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    ai = TaskAIService()
    history = session["history"]

    # Добавляем контекст в историю
    history.append({"role": "assistant", "content": json.dumps(session["last_statement"])})

    # Снова вызываем метод генерации, он примет историю
    new_statement = await ai.generate_statement(request.feedback, history)

    SessionStore.update(request.session_id, {
        "history": history + [{"role": "user", "content": request.feedback}],
        "last_statement": new_statement
    })

    return AIStatementResponse(statement=new_statement, session_id=request.session_id)


@gpt_router.post("/approve-and-upload")
async def approve_and_upload(
        request: ApproveUploadRequest,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db)
):
    session = SessionStore.get(request.session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    statement = session["last_statement"]
    user_id = request.user_id

    # Запускаем фоновую задачу, чтобы не блокировать ответ
    background_tasks.add_task(
        run_upload_pipeline,
        request.problem_id,
        statement,
        user_id,
        request.session_id,
        db
    )

    return {"status": "upload_started", "session_id": request.session_id}


@gpt_router.get("/upload-progress/{session_id}", response_model=UploadProgressResponse)
async def get_upload_progress(session_id: str):
    session = SessionStore.get(session_id)
    if not session:
        raise HTTPException(404, "Session not found")

    progress = session.get("upload_progress", {})
    return UploadProgressResponse(**progress)