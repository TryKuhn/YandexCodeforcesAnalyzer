"""Prompt builder for the code-fixing agent (build/upload error repair)."""
from typing import Dict, List

from api.user.gpt.services.files.file_registry import get_spec
from api.user.gpt.services.prompts.base import INCORRECT_SOLUTION_RULES

_INCORRECT_TAGS = {"WA", "TL", "ML", "RE", "RJ"}


def _verdict_mismatch_note(component: str) -> str:
    """Guidance for solution files that pass/fail against their expected tag.

    Polygon's package verification fails a solution that does not actually earn
    its tag (e.g. a ``TL``-tagged solution that passes every test). The fixer must
    change the ALGORITHM so the real verdict matches the tag — not the tag.
    """
    spec = get_spec(component)
    tag = spec.tag if spec else None
    if tag not in _INCORRECT_TAGS:
        return ""
    note = (
        f"\n\nЭто решение помечено тегом {tag} и ДОЛЖНО получать именно этот вердикт "
        f"на полном наборе тестов. Если ошибка вида «passed all tests but is tagged "
        f"as {tag}» / «expected {tag}» — значит решение НЕ соответствует тегу: измени "
        f"сам АЛГОРИТМ так, чтобы оно реально получало {tag} (нельзя менять тег или "
        f"добавлять искусственные задержки/аварии)."
        f"\n{INCORRECT_SOLUTION_RULES}"
    )
    return note


def build_system_prompt(
    component: str,
    error: str,
    previous_errors: List[str] | None = None,
    related_files: Dict[str, str] | None = None,
) -> str:
    """Build the system prompt instructing the model to repair ``component``'s code.

    Folds in any ``previous_errors`` (asking for a different approach), a note
    about ``related_files`` (incl. the generator/script opt-key mismatch behind
    testlib's "unused key" failures), and verdict-tag rules for incorrect
    solutions so a tag/verdict mismatch is fixed by changing the algorithm.
    """
    history_note = ""
    if previous_errors:
        history_note = (
            "\n\nПРЕДЫДУЩИЕ ПОПЫТКИ ИСПРАВЛЕНИЯ ТОЖЕ НЕ ПОМОГЛИ:\n"
            + "\n".join(f"- {e}" for e in previous_errors)
            + "\nПопробуй принципиально другой подход."
        )

    related_note = ""
    if related_files:
        names = ", ".join(related_files)
        related_note = (
            f"\n\nВ контексте приведены связанные файлы ({names}). НЕ переписывай их — "
            f"но приведи '{component}' в полное соответствие с ними. "
        )
        if component in ("generator", "script"):
            related_note += (
                "Частая причина такой ошибки — рассогласование именованных параметров "
                "(opt-ключей) между generator.cpp и скриптом генерации тестов: скрипт "
                "передаёт ключ, которого генератор не читает через opt<...>() (или "
                "наоборот). Сведи набор ключей к ТОЧНОМУ совпадению: для каждого ключа "
                "выбери одно из двух — либо добавь его чтение в генератор через "
                "opt<...>(), либо убери из скрипта. seed уместен для вариативности "
                "тестов, но если скрипт передаёт seed, генератор обязан читать "
                "opt<int>(\"seed\")."
            )

    return (
        f"Fix the {component} code for the Polygon judge system. "
        f"Current error: {error}{history_note}{related_note}"
        f"{_verdict_mismatch_note(component)} "
        "Return ONLY the corrected code without any explanation or markdown."
    )
