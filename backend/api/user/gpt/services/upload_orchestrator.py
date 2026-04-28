import asyncio
import logging
import re
import time
import traceback
from typing import Dict

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

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
PACKAGE_POLL_INTERVAL = 10  # секунд между проверками статуса пакета
PACKAGE_POLL_TIMEOUT = 600  # максимум 10 минут ждём пакет


async def _update_session(session_id: str, data: Dict, db: AsyncSession):
    """Обновляет поля сессии в БД"""
    await db.execute(update(AISession).where(AISession.id == session_id).values(**data))
    await db.commit()


def _make_polygon_name(model: str, statement: Dict, session_id: str) -> str:
    model_short = re.sub(r"[^a-z0-9]", "", model.split("/")[-1].lower())[:8]

    suffix = session_id[:4]

    timestamp = str(int(time.time()))[-5:]

    return f"{model_short}-task-{suffix}-{timestamp}"


async def run_upload_pipeline(session_id: str):
    """
    Этап UPLOADING: создаём задачу в Polygon, грузим файлы,
    коммитим, собираем пакет.
    """
    async with Session() as db:
        res = await db.get(AISession, session_id)
        if not res:
            return

        user_id = res.user_id
        statement = res.statement
        tech_data = res.technical_data
        model = res.model
        ai = TaskAIService()

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
            # 1. Создаём задачу
            polygon_name = _make_polygon_name(model, statement, session_id)
            problem_id = await create_problem(name=polygon_name, user_id=user_id, db=db)
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

            # 3. Технические файлы с авторетраями
            steps = [
                ("validator", set_validator, "validator", "validator.cpp", []),
                ("generator", set_generator, "generator", "generator.cpp", []),
                ("checker", set_checker, "checker", "checker.cpp", []),
                ("sol_main", set_solution, "solution_cpp", "solution.cpp", ["MA"]),
                ("sol_wa", set_solution, "wa_sol", "wa.cpp", ["WA"]),
                ("sol_tl", set_solution, "tl_sol", "tl.cpp", ["TL"]),
                ("sol_re", set_solution, "re_sol", "re.cpp", ["RE"]),
                ("sol_ml", set_solution, "ml_sol", "ml.cpp", ["ML"]),
            ]

            upload_errors = {}

            for step_name, upload_func, data_key, file_name, extra_args in steps:
                code = tech_data.get(data_key)
                if not code:
                    continue

                progress["current_step"] = f"Загрузка {file_name}..."
                await _update_session(session_id, {"progress": progress}, db)

                success = False
                last_error = None

                for attempt in range(1, MAX_RETRIES + 1):
                    try:
                        args = [problem_id, file_name, code, *extra_args, user_id, db]
                        await upload_func(*args)
                        success = True
                        break
                    except Exception as e:
                        last_error = str(e)
                        logger.warning(
                            f"[{session_id}] {step_name} attempt {attempt} failed: {e}"
                        )
                        progress["retries"] = attempt
                        progress["current_step"] = (
                            f"Ошибка в {file_name}, ИИ правит "
                            f"(попытка {attempt}/{MAX_RETRIES})..."
                        )
                        await _update_session(session_id, {"progress": progress}, db)

                        if attempt < MAX_RETRIES:
                            # ИИ пробует исправить
                            code = await ai.fix_code(
                                last_error, step_name, code, statement, model
                            )
                            # Сохраняем исправленный код в БД
                            tech_data[data_key] = code
                            await _update_session(
                                session_id, {"technical_data": tech_data}, db
                            )

                if not success:
                    # После 3 попыток — записываем ошибку и ждём ручного фикса
                    upload_errors[data_key] = {
                        "file_name": file_name,
                        "error": last_error,
                        "needs_manual_fix": True,
                    }

            # 4. Если есть файлы, которые не удалось загрузить — уходим в режим
            #    ожидания ручных правок
            if upload_errors:
                progress["status"] = "waiting_manual_fix"
                progress["current_step"] = (
                    "ИИ не смог исправить ошибки. Требуется ручная правка."
                )
                await _update_session(
                    session_id,
                    {
                        "progress": progress,
                        "upload_errors": upload_errors,
                        "stage": PipelineStage.FIXING_ERRORS,
                    },
                    db,
                )
                return  # Выходим — ждём действий пользователя

            # 5. Скрипт тестов
            if tech_data.get("script"):
                progress["current_step"] = "Загрузка скрипта тестов..."
                await _update_session(session_id, {"progress": progress}, db)
                await set_script(problem_id, "tests", tech_data["script"], user_id, db)

            # 6. Коммит
            progress["current_step"] = "Коммит изменений..."
            await _update_session(session_id, {"progress": progress}, db)
            await commit(problem_id, user_id, db)

            # 7. Сборка пакета
            await _build_and_poll_package(session_id, problem_id, user_id, progress, db)

        except Exception as e:
            progress["status"] = "failed"
            progress["error"] = str(e)
            progress["traceback"] = traceback.format_exc()
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
    progress["stage"] = PipelineStage.BUILDING_PACKAGE
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

    # Таймаут
    progress["status"] = "failed"
    progress["current_step"] = "Таймаут сборки пакета"
    await _update_session(
        session_id, {"progress": progress, "stage": PipelineStage.FAILED}, db
    )


async def retry_upload_after_manual_fix(session_id: str):
    async with Session() as db:
        res = await db.get(AISession, session_id)
        if not res:
            return

        upload_errors = res.upload_errors or {}
        tech_data = res.technical_data or {}
        statement = res.statement
        user_id = res.user_id
        model = res.model
        problem_id = res.polygon_problem_id
        ai = TaskAIService()

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
            step_map = {
                "validator": (set_validator, "validator.cpp", []),
                "generator": (set_generator, "generator.cpp", []),
                "checker": (set_checker, "checker.cpp", []),
                "solution_cpp": (set_solution, "solution.cpp", ["MA"]),
                "wa_sol": (set_solution, "wa.cpp", ["WA"]),
                "tl_sol": (set_solution, "tl.cpp", ["TL"]),
                "re_sol": (set_solution, "re.cpp", ["RE"]),
                "ml_sol": (set_solution, "ml.cpp", ["ML"]),
            }

            remaining_errors = {}

            for data_key, error_info in upload_errors.items():
                if data_key == "package":
                    # Ошибка пакета — просто пересобираем
                    continue

                if data_key not in step_map:
                    continue

                upload_func, file_name, extra_args = step_map[data_key]
                code = tech_data.get(data_key)
                if not code:
                    continue

                progress["current_step"] = f"Повторная загрузка {file_name}..."
                await _update_session(session_id, {"progress": progress}, db)

                success = False
                for attempt in range(1, MAX_RETRIES + 1):
                    try:
                        args = [problem_id, file_name, code, *extra_args, user_id, db]
                        await upload_func(*args)
                        success = True
                        break
                    except Exception as e:
                        last_error = str(e)
                        if attempt < MAX_RETRIES:
                            code = await ai.fix_code(
                                last_error, data_key, code, statement, model
                            )
                            tech_data[data_key] = code
                            await _update_session(
                                session_id, {"technical_data": tech_data}, db
                            )

                if not success:
                    remaining_errors[data_key] = error_info

            if remaining_errors:
                progress["status"] = "waiting_manual_fix"
                progress["current_step"] = "Ошибки остались после повторной попытки"
                await _update_session(
                    session_id,
                    {
                        "progress": progress,
                        "upload_errors": remaining_errors,
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
            progress["status"] = "failed"
            progress["error"] = str(e)
            await _update_session(
                session_id, {"progress": progress, "stage": PipelineStage.FAILED}, db
            )
