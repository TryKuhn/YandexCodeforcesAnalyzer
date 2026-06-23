"""Build the current Polygon package with AI auto-repair on failure.

Unlike the full wizard pipeline, this does NOT re-upload statement/settings — it
assumes the problem already exists on Polygon (the task tab). It pulls the
problem's files into the session (so the fixer has content), then runs the build
loop which, on FAILURE, locates the offending file and gives the AI up to 3
attempts to fix it (build/package_loop).
"""
import logging
import traceback

from api.user.gpt.services.build import package_loop
from api.user.gpt.services.build.pipeline import _apply_build_result
from api.user.gpt.services.build.scoring_groups import (parse_scoring_groups,
                                                        setup_groups_and_points,
                                                        subtasks_to_groups)
from api.user.gpt.services.chat.file_context import ensure_files_loaded
from api.user.gpt.services.generation import subtask_plan_gen
from api.user.gpt.services.sessions import update_session
from api.user.gpt.services.sync.samples_sync import upload_examples
from app.database import Session
from models.task.session import PipelineStage, TaskSession

logger = logging.getLogger(__name__)


async def run_build_with_repair(session_id: str) -> None:
    """Background entry: commit + build the package, auto-repairing on failure.

    Uploads manual sample tests (group 0) before the generated ones, and enables
    + configures groups/points on Polygon here because the chat path skips that
    setup.
    """
    async with Session() as db:
        session = await db.get(TaskSession, session_id)
        if not session or not session.polygon_problem_id:
            return

        await ensure_files_loaded(db, session)

        progress = {"status": "building", "current_step": "Запуск сборки пакета...",
                    "error": None}

        async def set_step(step: str) -> None:
            progress["current_step"] = step
            await update_session(db, session_id, {"progress": progress})

        await update_session(
            db, session_id,
            {"progress": progress, "stage": PipelineStage.BUILDING_PACKAGE},
        )

        try:
            problem_id = session.polygon_problem_id
            settings = dict(session.problem_settings or {})
            subtasks = settings.get("subtasks") or []
            groups_on = settings.get("enable_groups") or settings.get("enable_points")

            # Groups enabled but never planned (e.g. toggled on without generating
            # the scoring table) → plan subtasks now so groups/points actually get
            # configured, instead of silently building without them.
            if (groups_on and not subtasks
                    and not (session.statement or {}).get("scoring")):
                await set_step("Планирование подзадач...")
                subtasks = await subtask_plan_gen.generate(
                    session.statement or {}, session.model
                )
                if subtasks:
                    settings["subtasks"] = subtasks
                    await update_session(db, session_id, {"problem_settings": settings})

            if session.examples:
                await set_step("Загрузка примеров...")
                await upload_examples(
                    db, problem_id, session.user_id, session.examples,
                    group="0" if groups_on else None,
                )

            scoring_groups = []
            if groups_on:
                await set_step("Настройка групп и баллов...")
                scoring_groups = await setup_groups_and_points(
                    session_id, problem_id, session.user_id, settings,
                    (session.statement or {}).get("scoring"), db, subtasks=subtasks,
                )
            else:
                scoring_groups = parse_scoring_groups(
                    (session.statement or {}).get("scoring")
                )

            result = await package_loop.build_and_poll(
                db, session, scoring_groups=scoring_groups or None, set_step=set_step,
            )
            await _apply_build_result(
                db, session_id, session.polygon_problem_id, progress, result
            )
        except Exception as e:
            logger.exception(f"[{session_id}] build-with-repair failed: {e}")
            progress["status"] = "failed"
            progress["error"] = str(e)
            progress["traceback"] = traceback.format_exc()
            await update_session(
                db, session_id, {"progress": progress, "stage": PipelineStage.FAILED}
            )
