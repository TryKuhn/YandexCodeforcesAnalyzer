"""AI generation of a checker + validator from a parsed statement.

Moved out of ``polygon/archive/ai_files.py`` so that ``polygon/`` holds no AI
logic. Used by the olympiad-archive import flow: the model receives the
statement (legend, I/O formats, examples) and returns JSON describing a standard
or custom testlib checker plus a testlib validator.
"""
from __future__ import annotations

import logging
import re

from api.user.gpt.services.llm.client import llm
from api.user.gpt.services.llm.models import DEFAULT_MODEL
from api.user.polygon.archive.parser import Statement, render_section

logger = logging.getLogger(__name__)

STANDARD_CHECKERS = """\
std::wcmp.cpp  — сравнение последовательностей токенов (самый частый выбор)
std::lcmp.cpp  — сравнение строк (учитывает переводы строк, игнорирует хвостовые пробелы)
std::fcmp.cpp  — побайтовое сравнение файлов
std::ncmp.cpp  — сравнение последовательностей целых чисел (long long)
std::rcmp4.cpp — сравнение последовательностей чисел с плавающей точкой, погрешность 1e-4
std::rcmp6.cpp — то же, погрешность 1e-6
std::rcmp9.cpp — то же, погрешность 1e-9
std::yesno.cpp — единственный токен YES/NO (без учёта регистра)\
"""

SYSTEM_PROMPT = (
    "Ты — опытный автор задач для Codeforces Polygon. "
    "По условию задачи ты выбираешь чекер и пишешь валидатор на testlib. "
    "Отвечай СТРОГО одним JSON-объектом без пояснений и без markdown-ограждений."
)


def _statement_summary(st: Statement, max_len: int = 6000) -> str:
    """Build a truncated text summary of the statement for the prompt."""
    parts = [f"Название: {st.title or st.letter}"]
    if st.input_file != "stdin" or st.output_file != "stdout":
        parts.append(f"Файлы ввода/вывода: {st.input_file} / {st.output_file}")
    if st.legend:
        parts.append("Легенда:\n" + render_section(st.legend))
    if st.input_format:
        parts.append("Формат входных данных:\n" + render_section(st.input_format))
    if st.output_format:
        parts.append("Формат выходных данных:\n" + render_section(st.output_format))
    if st.scoring:
        parts.append("Система оценки:\n" + render_section(st.scoring))
    for i, (inp, outp) in enumerate(st.examples[:3], 1):
        parts.append(f"Пример {i}, ввод:\n{inp}\nвывод:\n{outp}")
    text = "\n\n".join(parts)
    return text[:max_len]


def _build_prompt(st: Statement) -> str:
    """Build the user prompt asking the model to pick a checker and write a validator."""
    return f"""Условие задачи (TeX-разметка из PDF, может содержать артефакты):

{_statement_summary(st)}

Задание:
1. Выбери чекер. Если подходит стандартный чекер Polygon — используй его:
{STANDARD_CHECKERS}
Если ответ неоднозначен (несколько правильных ответов, нужна проверка структуры) — напиши кастомный чекер на C++ с testlib.h.
Особый случай — задача на ОПТИМИЗАЦИЮ с частичной оценкой (открытые тесты,
в «Системе оценки» формула баллов от качества ответа): обязательно напиши
кастомный чекер-СКОРЕР — прочитай вывод участника из ouf, проверь его
корректность (структуру, ограничения), вычисли значение целевой функции
и выставь баллы через quitp(балл, "..."). Эталонный ответ жюри (ans) у таких
задач обычно ПУСТОЙ — не читай из него; опорное значение жюри, если оно есть,
бери из входных данных теста.
2. Напиши валидатор входных данных на C++ с testlib.h: построчно проверь формат и все ограничения из условия (диапазоны чисел, размеры, разделители, перевод строки в конце — inf.readEoln()/inf.readEof()).

Важно: подключай testlib строго как #include "testlib.h" (в кавычках, НЕ в угловых скобках — иначе компилятор Polygon его не найдёт).

Верни строго JSON:
{{
  "checker": {{"type": "standard", "name": "std::wcmp.cpp"}}
             ИЛИ {{"type": "custom", "code": "<полный код чекера на C++>"}},
  "validator": {{"code": "<полный код валидатора на C++>"}},
  "comment": "<1-2 предложения, почему такой выбор>"
}}"""


async def generate_checker_validator(st: Statement, model: str = DEFAULT_MODEL) -> dict:
    """Return {"checker": {...}, "validator": {...}, "comment": str}.

    Raises on API error or a response missing checker/validator. Angle-bracket
    ``#include <testlib.h>`` is normalised to quoted form because the Polygon
    compiler only finds testlib.h with ``#include "testlib.h"``.
    """
    result = await llm.ask(
        model,
        [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_prompt(st)},
        ],
        json_mode=True,
    )
    if "validator" not in result or "checker" not in result:
        raise ValueError("Ответ модели не содержит checker/validator")
    for part in (result.get("checker"), result.get("validator")):
        if isinstance(part, dict) and part.get("code"):
            part["code"] = re.sub(
                r'#include\s*<\s*testlib\.h\s*>', '#include "testlib.h"', part["code"]
            )
    return result
