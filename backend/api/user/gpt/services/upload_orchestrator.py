import traceback
from typing import Dict
from sqlalchemy.ext.asyncio import AsyncSession

from api.user.gpt.services.ai_service import TaskAIService
from api.user.gpt.services.session_store import SessionStore

from api.user.polygon.files.save_statement import save_statement
from api.user.polygon.files.gen.set_validator import set_validator
from api.user.polygon.files.gen.set_generator import set_generator
from api.user.polygon.files.gen.set_checker import set_checker
from api.user.polygon.files.gen.set_solution import set_solution
from api.user.polygon.files.gen.set_script import set_script
from api.user.polygon.commit.commit_problem import commit

MAX_RETRIES = 3

async def run_upload_pipeline(
    problem_id: int,
    statement: Dict,
    user_id: int,
    session_id: str,
    db: AsyncSession
):
    ai = TaskAIService()
    progress = {"status": "uploading", "current_step": "generating_tech"}
    SessionStore.update(session_id, {"upload_progress": progress})

    try:
        tech_data = await ai.generate_technical_stuff(statement)
        progress["current_step"] = "uploading_statement"
        SessionStore.update(session_id, {"upload_progress": progress})

        await save_statement(
            problem_id=problem_id, lang="russian",
            name=statement['name'], legend=statement['legend'],
            input_legend=statement['input'], output_legend=statement['output'],
            notes=statement.get('notes'), tutorial=statement.get('tutorial'),
            scoring="",
            interaction="",
            user_id=user_id, db=db
        )

        steps = [
            ("validator", set_validator, "validator", "val.cpp"),
            ("generator", set_generator, "generator", "gen.cpp"),
            ("checker", set_checker, "checker", "check.cpp"),
            ("solution", set_solution, "solution_cpp", "sol.cpp", "MA"),
        ]

        for step in steps:
            step_name = step[0]
            upload_func = step[1]
            data_key = step[2]
            file_name = step[3]
            extra_args = step[4:] if len(step) > 4 else []

            progress["current_step"] = step_name
            SessionStore.update(session_id, {"upload_progress": progress})

            success = False
            attempt = 0
            while attempt < MAX_RETRIES and not success:
                try:
                    args = [problem_id, file_name, tech_data[data_key], *extra_args, user_id, db]
                    await upload_func(*args)
                    success = True
                except Exception as e:
                    attempt += 1
                    error_msg = str(e)
                    progress["error"] = error_msg
                    progress["retries"] = attempt
                    SessionStore.update(session_id, {"upload_progress": progress})

                    if attempt < MAX_RETRIES:
                        # Self-healing
                        fixed = await ai.fix_code(error_msg, step_name, tech_data[data_key], statement)
                        tech_data[data_key] = fixed
                    else:
                        raise

        # Скрипт тестов
        progress["current_step"] = "script"
        await set_script(problem_id, "tests", tech_data['script'], user_id, db)

        # Коммит
        progress["current_step"] = "committing"
        await commit(problem_id, user_id, db)

        progress["status"] = "done"
        progress["current_step"] = None
        SessionStore.update(session_id, {"upload_progress": progress})

    except Exception as e:
        progress["status"] = "failed"
        progress["error"] = str(e)
        progress["traceback"] = traceback.format_exc()
        SessionStore.update(session_id, {"upload_progress": progress})