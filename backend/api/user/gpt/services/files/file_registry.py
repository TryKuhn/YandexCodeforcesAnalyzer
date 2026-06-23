"""Single source of truth for the technical-file taxonomy.

Maps each logical ``file_type`` to its filename, its Polygon "category" (which
Polygon endpoint syncs it), an optional solution tag, and which problem types it
applies to. Generation, sync and build layers all consult this registry instead
of hard-coding file lists, so adding a file type is a one-line change.

REGISTRY order matters: it is also the generation/upload order within a pack.
Note that the output-only ``scorer`` is registered under the ``checker``
category because Polygon sets the scorer as the problem's checker.
"""
from dataclasses import dataclass, field

from api.user.gpt.services.ai_file_helpers import FILE_NAME_MAP
from models.task.session import ProblemType

R = ProblemType.REGULAR
I = ProblemType.INTERACTIVE
O = ProblemType.OUTPUT_ONLY


@dataclass(frozen=True)
class FileSpec:
    """One technical file: its logical type, Polygon sync ``category``
    (validator|generator|script|checker|interactor|solution), the set of
    ``ProblemType``s it applies to, and a Polygon solution ``tag`` (only for
    ``category == "solution"``)."""
    file_type: str
    category: str
    applies_to: set
    tag: str | None = None

    @property
    def filename(self) -> str:
        """Polygon filename for this file type."""
        return FILE_NAME_MAP.get(self.file_type, self.file_type)


REGISTRY: list[FileSpec] = [
    FileSpec("validator", "validator", {R, I, O}),
    FileSpec("generator", "generator", {R, I, O}),
    FileSpec("script", "script", {R, I, O}),
    FileSpec("checker", "checker", {R, I}),
    FileSpec("interactor", "interactor", {I}),
    FileSpec("scorer", "checker", {O}),
    FileSpec("jury_answer", "solution", {O}, tag="MA"),
    FileSpec("solution_cpp", "solution", {R, I}, tag="MA"),
    FileSpec("solution_py", "solution", {R, I}, tag="OK"),
    FileSpec("wa_sol", "solution", {R, I}, tag="WA"),
    FileSpec("tl_sol", "solution", {R, I}, tag="TL"),
    FileSpec("re_sol", "solution", {R, I}, tag="RE"),
    FileSpec("ml_sol", "solution", {R, I}, tag="ML"),
]

_BY_TYPE: dict[str, FileSpec] = {s.file_type: s for s in REGISTRY}


def get_spec(file_type: str) -> FileSpec | None:
    """Return the FileSpec for a file type, or None if unknown."""
    return _BY_TYPE.get(file_type)


def applicable_types(problem_type: str | ProblemType) -> list[str]:
    """File types that make up the pack for a given problem type, in pack order."""
    pt = ProblemType(problem_type) if not isinstance(problem_type, ProblemType) else problem_type
    return [s.file_type for s in REGISTRY if pt in s.applies_to]


def category(file_type: str) -> str | None:
    """Polygon sync category for a file type, or None if unknown."""
    spec = _BY_TYPE.get(file_type)
    return spec.category if spec else None


def solution_tag(file_type: str) -> str | None:
    """Polygon solution tag for a file type, or None if unknown or not a solution."""
    spec = _BY_TYPE.get(file_type)
    return spec.tag if spec else None
