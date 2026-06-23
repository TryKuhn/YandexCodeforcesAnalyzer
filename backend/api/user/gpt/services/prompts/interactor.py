"""Prompt for generating interactor.cpp (interactive problems)."""
from .base import NO_FENCES, TESTLIB_INTRO

SYSTEM_PROMPT = (
    f"{TESTLIB_INTRO}\n"
    "Напиши interactor.cpp для ИНТЕРАКТИВНОЙ задачи Polygon, используя testlib.h. "
    "Интерактор должен: вызвать registerInteraction(argc, argv); читать вход (inf), "
    "обмениваться с программой участника (читать её запросы из ouf, отвечать через cout с fflush), "
    "проверять корректность запросов и лимит на их число, и завершиться quitf(_ok/_wa, ...). "
    "Поддержи адаптивный или неадаптивный режим в соответствии с условием. "
    f"{NO_FENCES}"
)
