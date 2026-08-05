"""Language registry and compilation."""

from .compile import CompileResult, compile_source
from .registry import (
    CPP,
    PYTHON,
    Language,
    UnknownLanguage,
    all_languages,
    get,
    register,
)

__all__ = [
    "CPP",
    "PYTHON",
    "CompileResult",
    "Language",
    "UnknownLanguage",
    "all_languages",
    "compile_source",
    "get",
    "register",
]
