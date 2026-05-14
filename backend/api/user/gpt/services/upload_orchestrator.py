import asyncio
import logging
import re
import time
import traceback
from typing import Any, Callable, Dict

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from api.user.gpt.services.ai_file_helpers import (
    get_session_files, mark_uploaded, upsert_ai_file)
from api.user.gpt.services.ai_service import TaskAIService
from api.user.polygon.commit.commit_problem import commit
from api.user.polygon.commit.get_packages import get_packages
from api.user.polygon.create_problem import create_problem
from api.user.polygon.files.gen.set_checker import set_checker
from api.user.polygon.files.gen.set_generator import set_generator
from api.user.polygon.files.gen.set_script import set_script
from api.user.polygon.files.gen.set_solution import set_solution
from api.user.polygon.files.gen.set_validator import set_validator
from api.user.polygon.files.save_statement import save_statement
from app.database import Session
from models.ai.ai_session import AISession, PipelineStage

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
PACKAGE_POLL_INTERVAL = 10
PACKAGE_POLL_TIMEOUT = 600

STEP_MAP: list[tuple[str, Callable[..., Any], str, str, list[str]]] = [
    ("validator", set_validator, "validator",     "validator.cpp", []),
    ("generator", set_generator, "generator",     "generator.cpp", []),
    ("checker",   set_checker,   "checker",       "checker.cpp",   []),
    ("sol_main",  set_solution,  "solution_cpp",  "solution.cpp",  ["MA"]),
    ("sol_py",    set_solution,  "solution_py",   "solution_py.py", ["OK"]),
    ("sol_wa",    set_solution,  "wa_sol",        "wa.cpp",        ["WA"]),
    ("sol_tl",    set_solution,  "tl_sol",        "tl.cpp",        ["TL"]),
    ("sol_re",    set_solution,  "re_sol",        "re.cpp",        ["RE"]),
    ("sol_ml",    set_solution,  "ml_sol",        "ml.cpp",        ["ML"]),
]


async def _update_session(session_id: str, data: Dict, db: AsyncSession):
    await db.execute(update(AISession).where(AISession.id == session_id).values(**data))
    await db.commit()


def _make_polygon_name(model: str, statement: Dict, session_id: str) -> str:
    model_short = re.sub(r"[^a-z0-9]", "", model.split("/")[-1].lower())[:8]
    suffix = session_id[:4]
    timestamp = str(int(time.time()))[-5:]
    return f"{model_short}-task-{suffix}-{timestamp}"


async def _upload_steps(
    session_id: str,
    problem_id: int,
    user_id: int,
    statement: Dict,
    model: str,
    progress: Dict,
    db: AsyncSession,
) -> dict:
    """
    Загружает технические файлы на Polygon.
    Пропускает файлы, у которых AIGeneratedFile.uploaded == True.
    Возвращает словарь upload_errors для файлов, которые не удалось загрузить.
    """
    ai = TaskAIService()
    session_files = await get_session_files(db, session_id)
    upload_errors = {}

    for step_name, upload_func, data_key, file_name, extra_args in STEP_MAP:
        file_obj = session_files.get(data_key)
        if not file_obj:
            continue

        # Пропускаем, если файл уже загружен в этой версии
        if file_obj.uploaded:
            logger.info(f"[{session_id}] Skipping already-uploaded {file_name}")
            continue

        code = file_obj.content
        progress["current_step"] = f"Загрузка {file_name}..."
        await _update_session(session_id, {"progress": progress}, db)

        success = False
        last_error = None
        error_history: list[str] = []

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                args = [problem_id, file_name, code, *extra_args, user_id, db]
                await upload_func(*args)
                success = True
                break
            except Exception as e:
                last_error = str(e)
                logger.warning(f"[{session_id}] {step_name} attempt {attempt} failed: {e}")
                progress["retries"] = attempt
                progress["current_step"] = (
                    f"Ошибка в {file_name}, ИИ правит "
                    f"(попытка {attempt}/{MAX_RETRIES})..."
                )
                await _update_session(session_id, {"progress": progress}, db)

                if attempt < MAX_RETRIES:
                    try:
                        code = await ai.fix_code(
                            last_error, step_name, code, statement, model,
                            previous_errors=error_history if error_history else None,
                        )
                        error_history.append(last_error)
                        await upsert_ai_file(db, session_id, data_key, code, uploaded=False)
                        await db.commit()
                    except Exception as fix_err:
                        logger.warning(f"[{session_id}] AI fix failed for {step_name}: {fix_err}")
                else:
                    error_history.append(last_error)

        if success:
            logger.info(f"[{session_id}] Uploaded {file_name}")
            await mark_uploaded(db, session_id, data_key)
            await db.commit()
        else:
            logger.error(
                f"[{session_id}] Failed to upload {file_name} after {MAX_RETRIES} attempts: {last_error}"
            )
            upload_errors[data_key] = {
                "file_name": file_name,
                "error": last_error,
                "needs_manual_fix": True,
            }

    # Скрипт тестов
    script_obj = session_files.get("script")
    if script_obj and not script_obj.uploaded:
        progress["current_step"] = "Загрузка скрипта тестов..."
        await _update_session(session_id, {"progress": progress}, db)
        try:
            await set_script(problem_id, "tests", script_obj.content, user_id, db)
            await mark_uploaded(db, session_id, "script")
            await db.commit()
        except Exception as e:
            logger.error(f"[{session_id}] Failed to upload script: {e}")
            upload_errors["script"] = {
                "file_name": "script.txt",
                "error": str(e),
                "needs_manual_fix": True,
            }

    return upload_errors


async def run_upload_pipeline(session_id: str):
    """
    Этап UPLOADING: создаём задачу в Polygon (если не создана), грузим файлы,
    коммитим, собираем пакет.
    """
    async with Session() as db:
        res = await db.get(AISession, session_id)
        if not res:
            return

        user_id = res.user_id
        statement = res.statement
        model = res.model

        progress = {
            "status": "uploading",
            "current_step": "Создание задачи в Polygon...",
            "retries": 0,
            "error": None,
        }
        await _update_session(
            session_id, {"progress": progress, "stage": PipelineStage.UPLOADING}, db
        )

        try:
            # 1. Создаём задачу только если ещё не создана
            if res.polygon_problem_id:
                problem_id = res.polygon_problem_id
                logger.info(f"[{session_id}] Reusing existing Polygon problem {problem_id}")
            else:
                polygon_name = _make_polygon_name(model, statement, session_id)
                logger.info(f"[{session_id}] Creating Polygon problem '{polygon_name}'")
                problem_id = await create_problem(name=polygon_name, user_id=user_id, db=db)
                logger.info(f"[{session_id}] Problem created: polygon_id={problem_id}")
                await _update_session(session_id, {"polygon_problem_id": problem_id}, db)

            # 2. Условие
            progress["current_step"] = "Загрузка условия..."
            await _update_session(session_id, {"progress": progress}, db)
            await save_statement(
                problem_id=problem_id,
                lang="russian",
                name=statement["name"],
                legend=statement["legend"],
                input_legend=statement["input"],
                output_legend=statement["output"],
                notes=statement.get("notes"),
                tutorial=statement.get("tutorial"),
                scoring="",
                interaction="",
                user_id=user_id,
                db=db,
            )

            # 3. Технические файлы
            upload_errors = await _upload_steps(
                session_id, problem_id, user_id, statement, model, progress, db
            )

            if upload_errors:
                progress["status"] = "waiting_manual_fix"
                progress["current_step"] = "ИИ не смог исправить ошибки. Требуется ручная правка."
                await _update_session(
                    session_id,
                    {
                        "progress": progress,
                        "upload_errors": upload_errors,
                        "stage": PipelineStage.FIXING_ERRORS,
                    },
                    db,
                )
                return

            # 4. Коммит
            progress["current_step"] = "Коммит изменений..."
            await _update_session(session_id, {"progress": progress}, db)
            await commit(problem_id, user_id, db)

            # 5. Сборка пакета
            await _build_and_poll_package(session_id, problem_id, user_id, progress, db)

        except Exception as e:
            logger.exception(f"[{session_id}] Upload pipeline failed: {e}")
            progress["status"] = "failed"
            progress["error"] = str(e)
            progress["traceback"] = traceback.format_exc()
            await _update_session(
                session_id, {"progress": progress, "stage": PipelineStage.FAILED}, db
            )


async def retry_upload_after_manual_fix(session_id: str):
    """
    Повторная загрузка после ручных правок (или доработки из DONE).
    Загружает только файлы с uploaded=False — то есть изменённые или ранее
    не загруженные. Задачу на Polygon не пересоздаёт.
    """
    async with Session() as db:
        res = await db.get(AISession, session_id)
        if not res:
            return

        statement = res.statement
        user_id = res.user_id
        model = res.model
        problem_id = res.polygon_problem_id

        if not problem_id:
            logger.error(f"[{session_id}] retry_upload called but polygon_problem_id is not set")
            await _update_session(
                session_id,
                {
                    "progress": {"status": "failed", "error": "Polygon problem ID not set"},
                    "stage": PipelineStage.FAILED,
                },
                db,
            )
            return

        progress = {
            "status": "uploading",
            "current_step": "Повторная загрузка исправленных файлов...",
            "retries": 0,
            "error": None,
        }
        await _update_session(
            session_id, {"progress": progress, "stage": PipelineStage.UPLOADING}, db
        )

        try:
            upload_errors = await _upload_steps(
                session_id, problem_id, user_id, statement, model, progress, db
            )

            if upload_errors:
                progress["status"] = "waiting_manual_fix"
                progress["current_step"] = "Ошибки остались после повторной попытки"
                await _update_session(
                    session_id,
                    {
                        "progress": progress,
                        "upload_errors": upload_errors,
                        "stage": PipelineStage.FIXING_ERRORS,
                    },
                    db,
                )
                return

            await _update_session(session_id, {"upload_errors": {}}, db)

            progress["current_step"] = "Коммит изменений..."
            await _update_session(session_id, {"progress": progress}, db)
            await commit(problem_id, user_id, db)

            await _build_and_poll_package(session_id, problem_id, user_id, progress, db)

        except Exception as e:
            logger.exception(f"[{session_id}] Retry pipeline failed: {e}")
            progress["status"] = "failed"
            progress["error"] = str(e)
            await _update_session(
                session_id, {"progress": progress, "stage": PipelineStage.FAILED}, db
            )


async def _build_and_poll_package(
    session_id: str,
    problem_id: int,
    user_id: int,
    progress: Dict,
    db: AsyncSession,
):
    from api.user.polygon.commit.build_package import \
        build_package as polygon_build_package

    progress["current_step"] = "Запуск сборки пакета..."
    await _update_session(
        session_id, {"progress": progress, "stage": PipelineStage.BUILDING_PACKAGE}, db
    )

    await polygon_build_package(problem_id=problem_id, user_id=user_id, db=db)

    elapsed = 0
    while elapsed < PACKAGE_POLL_TIMEOUT:
        await asyncio.sleep(PACKAGE_POLL_INTERVAL)
        elapsed += PACKAGE_POLL_INTERVAL

        packages = await get_packages(problem_id, user_id, db)
        if not packages:
            continue

        latest = packages[-1]
        state = latest.get("state", "PENDING")
        package_id = latest.get("id")

        progress["current_step"] = f"Сборка пакета: {state}..."
        await _update_session(session_id, {"progress": progress}, db)

        if state == "READY":
            logger.info(
                f"[{session_id}] Package built: polygon_id={problem_id} package_id={package_id}"
            )
            progress["status"] = "done"
            progress["current_step"] = (
                f"Задача создана! Polygon ID: {problem_id}, Package: {package_id}"
            )
            await _update_session(
                session_id,
                {
                    "progress": progress,
                    "stage": PipelineStage.DONE,
                    "package_id": package_id,
                },
                db,
            )
            return

        elif state == "FAILED":
            error_comment = latest.get("comment", "Неизвестная ошибка сборки пакета")
            logger.error(f"[{session_id}] Package build failed: {error_comment}")
            progress["status"] = "waiting_manual_fix"
            progress["current_step"] = "Ошибка сборки пакета"
            progress["error"] = error_comment
            await _update_session(
                session_id,
                {
                    "progress": progress,
                    "stage": PipelineStage.FIXING_ERRORS,
                    "upload_errors": {
                        "package": {
                            "error": error_comment,
                            "needs_manual_fix": True,
                        }
                    },
                },
                db,
            )
            return

    logger.error(f"[{session_id}] Package build timed out after {PACKAGE_POLL_TIMEOUT}s")
    progress["status"] = "failed"
    progress["current_step"] = "Таймаут сборки пакета"
    await _update_session(
        session_id, {"progress": progress, "stage": PipelineStage.FAILED}, db
    )
