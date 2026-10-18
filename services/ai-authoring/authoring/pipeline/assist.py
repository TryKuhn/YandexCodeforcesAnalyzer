"""Synchronous helpers: a solution draft for the file form, checker+validator
for the archive importer (which has a statement but no session)."""
from __future__ import annotations

import asyncio
import re

from authoring.llm import prompts
from authoring.llm.client import LLM
from authoring.llm.protocol import FileEdit, StandardChecker, parse, single_file

SKIP_RE = re.compile(r"^\s*SKIP\s*:?\s*(.*)$", re.IGNORECASE | re.DOTALL)

SOLUTION_DRAFT_SYSTEM = prompts.single_file_system(
    "Напиши решение задачи с заданным тегом (ожидаемым вердиктом).",
    prompts.SOLUTION_TAG_RULES
    + " Если для этой задачи нельзя честно гарантировать нужный вердикт настоящим алгоритмом -- "
    "верни ровно одну строку `SKIP: <причина по-русски>` вместо кода.",
)


async def solution_draft(llm: LLM, model: str, dossier: str, *, tag: str, name: str,
                         instruction: str | None) -> dict:
    task = f"Тег: {tag}. Имя файла: {name}." + (f"\nПожелания автора: {instruction}" if instruction else "")
    completion = await llm.complete(model, prompts.file_messages(SOLUTION_DRAFT_SYSTEM, dossier, task))
    skip = SKIP_RE.match(completion.text.strip())
    if skip and "<file" not in completion.text:
        return {"skipped": True, "reason": skip.group(1).strip()}
    edit = single_file(completion.text, role="solution")
    return {"skipped": False, "code": edit.content, "name": name, "tag": tag}


def statement_dossier(st: dict) -> str:
    parts = [f"# Задача «{st.get('name') or ''}»"]
    if st.get("time_limit") or st.get("memory_limit"):
        parts.append(f"TL: {st.get('time_limit')} мс, ML: {st.get('memory_limit')} МБ")
    if (st.get("input_file") or "stdin") != "stdin" or (st.get("output_file") or "stdout") != "stdout":
        parts.append(f"Файлы ввода/вывода: {st.get('input_file')} / {st.get('output_file')}")
    for key, label in (("legend", "Легенда"), ("input", "Формат ввода"), ("output", "Формат вывода"),
                       ("scoring", "Система оценки"), ("notes", "Примечание")):
        if st.get(key):
            parts.append(f"## {label}\n{st[key]}")
    for i, example in enumerate(st.get("examples") or [], 1):
        if len(example) == 2:
            parts.append(f"## Пример {i}\nВвод:\n```\n{example[0]}\n```\nВывод:\n```\n{example[1]}\n```")
    return "\n\n".join(parts)


async def checker_validator(llm: LLM, model: str, statement: dict) -> dict:
    dossier = statement_dossier(statement)
    checker_call = llm.complete(model, prompts.file_messages(prompts.CHECKER_SYSTEM, dossier))
    validator_call = llm.complete(model, prompts.file_messages(prompts.VALIDATOR_SYSTEM, dossier))
    checker_completion, validator_completion = await asyncio.gather(checker_call, validator_call)

    parsed = parse(checker_completion.text)
    checker: dict = {"type": "standard", "name": "std::wcmp.cpp"}
    for edit in parsed.edits:
        if isinstance(edit, StandardChecker):
            checker = {"type": "standard", "name": edit.name}
            break
        if isinstance(edit, FileEdit):
            checker = {"type": "custom", "code": edit.content}
            break
    validator = single_file(validator_completion.text, role="validator")
    return {"checker": checker, "validator": {"code": validator.content}, "comment": parsed.reply}
