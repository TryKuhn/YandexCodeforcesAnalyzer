"""Prompt for task-scope chat modify: pick & rewrite the relevant files.

The model is shown every current file and the user's request, and returns a JSON
object containing ONLY the files that actually change (file_type -> full code).
"""
import json
from typing import Dict

SYSTEM_PROMPT = (
    "Ты — эксперт по задачам Polygon. Пользователь хочет доработать уже созданную задачу. "
    "Проанализируй его запрос и обнови только те файлы, которых касаются изменения. "
    "Верни JSON, где ключи — имена изменённых файлов (из набора: "
    "validator, generator, checker, interactor, scorer, jury_answer, solution_cpp, "
    "solution_py, wa_sol, tl_sol, re_sol, ml_sol, script), "
    "а значения — полные обновлённые версии этих файлов (чистый код, без markdown). "
    "Не включай в ответ файлы, которые не нужно менять. "
    "НО если пользователь просит создать или сгенерировать конкретный файл "
    "(например «сгенерируй решение»), верни его полную версию, даже если сейчас "
    "он пустой или отсутствует.\n\n"
    "ОБЯЗАТЕЛЬНЫЕ ПРАВИЛА:\n"
    "- Файл `script` — это Freemarker-скрипт генерации тестов. Вызывай генератор СТРОГО "
    "как `generator` (имя source-файла generator.cpp БЕЗ расширения; Polygon иначе выдаёт "
    "ошибку «use source file name without extension»). НЕ используй `gen`, `generator.cpp`, "
    "`gen.cpp`. Каждая строка теста: `generator <параметры> > $`.\n"
    "- C++-файлы (validator/generator/checker/interactor/scorer/решения) подключают testlib "
    "строго как #include \"testlib.h\" (в кавычках, не в угловых скобках).\n"
    "- Значения в JSON — чистый исходный код без markdown-ограждений (никаких ```)."
)


def build_user_prompt(statement: Dict, files: Dict[str, str], message: str) -> str:
    """Build the user prompt with the statement, all current files, and the request."""
    files_text = "\n\n".join(
        f"=== {key} ===\n{content}" for key, content in files.items()
    )
    return (
        f"Условие задачи:\n{json.dumps(statement, ensure_ascii=False)}\n\n"
        f"Текущие файлы:\n{files_text}\n\n"
        f"Запрос пользователя: {message}"
    )
