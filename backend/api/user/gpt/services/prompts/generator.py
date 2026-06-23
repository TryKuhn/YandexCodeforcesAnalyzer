"""Prompt for generating generator.cpp (testlib)."""
import json
from typing import Dict

from .base import NO_FENCES, TESTLIB_INTRO

SYSTEM_PROMPT = (
    f"{TESTLIB_INTRO}\n"
    "Напиши generator.cpp для задачи Polygon, используя testlib.h.\n"
    "ПРАВИЛА ПАРАМЕТРОВ (критично для совместимости со скриптом генерации тестов):\n"
    "- Вызови registerGen(argc, argv, 1) — testlib сам инициализирует rnd из аргументов "
    "командной строки, поэтому тесты с разными параметрами уже различаются.\n"
    "- Принимай именованные параметры через opt<тип>(\"имя\") из testlib "
    "(например: int n = opt<int>(\"n\"); int maxLen = opt<int>(\"maxLen\");).\n"
    "- ВАЖНО: генератор и скрипт генерации тестов должны быть СОГЛАСОВАНЫ — генератор "
    "обязан прочитать через opt РОВНО те ключи, которые передаёт скрипт, и не больше. "
    "Если опустить или добавить лишний ключ, testlib падает с ошибкой «unused key».\n"
    "- Если в плане тестов указано, что нужен seed — ОБЯЗАТЕЛЬНО прочитай его "
    "(int seed = opt<int>(\"seed\");) и задействуй; иначе скрипт передаст seed, "
    "а генератор его не прочитает → «unused key 'seed'».\n"
    "- В начале файла в комментарии (на английском) перечисли принимаемые параметры, "
    "например: // params: n, minLen, maxLen.\n"
    "Печатай корректный вход, строго соответствующий условию и его ограничениям. "
    "Используй rnd из testlib для случайности (rnd.next(lo, hi)). "
    f"{NO_FENCES}"
)


def build_user_prompt(statement: Dict, plan_text: str | None = None) -> str:
    """User prompt for the generator — includes the pre-thought test plan so the
    generator reads exactly the planned opt parameters."""
    parts = [f"Условие задачи:\n{json.dumps(statement, ensure_ascii=False)}"]
    if plan_text:
        parts.append(plan_text + "\nРеализуй чтение РОВНО этих параметров через opt.")
    return "\n\n".join(parts)
