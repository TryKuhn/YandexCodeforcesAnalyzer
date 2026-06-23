"""Prompt for generating the jury reference solver (output-only problems).

Polygon has no API to upload jury answers directly: the *.a answer files are
produced by running the MAIN (tag MA) solution during package build. So for an
output-only problem the "jury answer" is just a correct reference solver whose
output IS the jury answer.
"""
from .base import NO_FENCES

SYSTEM_PROMPT = (
    "Ты — эксперт по разработке OUTPUT-ONLY задач для Polygon. "
    "Напиши эталонное (jury) решение на C++ для этой задачи. "
    "Его вывод по входным данным будет считаться ответом жюри (файл *.a), "
    "относительно которого чекер-скорер оценивает ответ участника. "
    "Решение должно давать оптимальный/эталонный ответ строго по условию. "
    f"{NO_FENCES}"
)
