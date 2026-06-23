"""Prompt for generating checker.cpp (testlib)."""
from .base import NO_FENCES, TESTLIB_INTRO

SYSTEM_PROMPT = (
    f"{TESTLIB_INTRO}\n"
    "Напиши checker.cpp для задачи Polygon, используя testlib.h. "
    "Чекер должен: вызвать registerTestlibCmd(argc, argv), читать вход (inf), ответ жюри (ans) "
    "и ответ участника (ouf), сравнить их по правилам условия и завершиться "
    "quitf(_ok, ...) / quitf(_wa, ...). "
    "Если у задачи возможно несколько правильных ответов — проверяй корректность ответа участника "
    "относительно входа, а не побитовое совпадение с ответом жюри. "
    f"{NO_FENCES}"
)

INTERACTIVE_SYSTEM_PROMPT = (
    f"{TESTLIB_INTRO}\n"
    "Напиши checker.cpp для ИНТЕРАКТИВНОЙ задачи Polygon. "
    "В интерактивных задачах основную проверку выполняет интерактор; чекер обычно читает "
    "финальный вердикт/счёт, записанный интерактором, и завершается соответствующим quitf. "
    "Сделай чекер согласованным с протоколом интерактора. "
    f"{NO_FENCES}"
)
