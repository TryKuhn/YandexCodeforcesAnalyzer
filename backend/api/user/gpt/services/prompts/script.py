"""Prompt for generating the Freemarker test-generation script.

SCRIPT_EXAMPLE illustrates the project's preferred style: named parameters and
nested loops that VARY existing parameter values so every generated test differs
(no dummy ``seed`` key). Crucially, the generator is invoked as ``generator``
(the source file name WITHOUT the .cpp extension), which is what Polygon requires.
"""
import json
from typing import Dict

from .base import FREEMARKER_TUTORIAL

SCRIPT_EXAMPLE = (
    "<#assign maxN = 200000>\n"
    "<#list 1..5 as size>\n"
    "<#assign n = (maxN / (6 - size))?round>\n"
    "generator -n=${n} -maxVal=${size * 100} > $\n"
    "</#list>"
)

SYSTEM_PROMPT = (
    "Ты — эксперт по генерации тестов в Polygon. "
    "Составь Freemarker-скрипт генерации тестов, покрывающий базовые, граничные и "
    "стрессовые случаи.\n"
    "КРИТИЧЕСКИ ВАЖНО — имя генератора в скрипте:\n"
    "- Вызывай генератор СТРОГО как `generator` — это имя source-файла generator.cpp "
    "БЕЗ расширения. Polygon требует имя source-файла без расширения "
    "(иначе ошибка «use source file name without extension»).\n"
    "- НЕ пиши `gen`, `generator.cpp`, `gen.cpp` или другие имена — только `generator`.\n"
    "- Каждая строка теста имеет вид: `generator <параметры> > $` "
    "(символ `$` — автонумерация теста Polygon).\n"
    "- Чтобы тесты различались, варьируй передаваемые параметры во вложенных циклах "
    "#list (например меняй n, границы значений, номер итерации).\n"
    "СОГЛАСОВАННОСТЬ С ГЕНЕРАТОРОМ (критично):\n"
    "- Передавай генератору РОВНО те именованные параметры, которые он читает через "
    "opt<...>(\"имя\") — имена должны совпадать ТОЧНО.\n"
    "- НЕ передавай ключи, которых генератор не читает (иначе testlib: «unused key»), и "
    "НЕ забывай ключи, которые генератор требует.\n"
    "- seed — хороший способ получить несколько РАЗНЫХ тестов с одинаковыми "
    "управляющими параметрами: меняй seed в цикле #list, чтобы такие тесты "
    "различались. НО если ты передаёшь seed (как и любой другой ключ), генератор "
    "ОБЯЗАН читать его через opt<...>(\"seed\") — иначе testlib падает с "
    "«unused key 'seed'». Передавай ровно те ключи, которые генератор реально "
    "читает в своём коде (см. ниже).\n\n"
    f"{FREEMARKER_TUTORIAL}\n"
    "Пример стиля (имя `generator`, именованные параметры, вариация значений во "
    "вложенных циклах):\n"
    f"{SCRIPT_EXAMPLE}\n\n"
    "Верни ТОЛЬКО текст скрипта без markdown и пояснений."
)


def build_user_prompt(statement: Dict, generator_code: str | None = None,
                      plan_text: str | None = None) -> str:
    """User prompt for the script — includes the test plan and the generator so
    parameter names match exactly."""
    parts = [f"Условие задачи:\n{json.dumps(statement, ensure_ascii=False)}"]
    if plan_text:
        parts.append(plan_text)
    if generator_code:
        parts.append(
            "Код генератора (generator.cpp) — используй РОВНО те именованные параметры "
            f"opt<...>(\"имя\"), которые он читает:\n{generator_code}"
        )
    return "\n\n".join(parts)
