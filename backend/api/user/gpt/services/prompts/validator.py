"""Prompt for generating validator.cpp (testlib)."""
from .base import NO_FENCES, TESTLIB_INTRO

SYSTEM_PROMPT = (
    f"{TESTLIB_INTRO}\n"
    "Напиши validator.cpp для задачи Polygon, используя testlib.h. "
    "Валидатор должен: через registerValidation(argc, argv) проверить ВЕСЬ формат входных данных "
    "строго по условию — типы, диапазоны (inf.readInt(lo, hi, \"name\")), разделители "
    "(readSpace/readEoln), отсутствие лишних данных (readEof в конце). "
    "Проверяй все ограничения из условия. "
    f"{NO_FENCES}"
)
