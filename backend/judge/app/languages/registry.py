"""Languages we can compile and run, and their fair limits."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Language:
    """One supported language, described by data rather than by code."""

    id: str
    name: str
    source_name: str
    run_argv: tuple[str, ...]

    # None means nothing to compile, the source runs as is
    compile_argv: tuple[str, ...] | None = None

    # interpreted languages need more time and memory for the same algorithm
    tl_multiplier: float = 1.0
    ml_multiplier: float = 1.0

    # compilation is our own trusted step, so it gets a separate, looser budget
    compile_time_ms: int = 10_000
    compile_memory_kb: int = 512 * 1024

    # g++ spawns cc1plus, so compilation cannot be limited to a single process
    compile_processes: int = 16

    extra_files: tuple[str, ...] = field(default_factory=tuple)

    @property
    def needs_compilation(self) -> bool:
        return self.compile_argv is not None


CPP = Language(
    id="cpp",
    name="C++ 17 (g++)",
    source_name="main.cpp",
    # -O2 matches what Codeforces and Polygon use, so timings stay comparable
    compile_argv=("g++", "-O2", "-std=c++17", "-o", "main", "main.cpp"),
    run_argv=("./main",),
)

PYTHON = Language(
    id="python",
    name="Python 3",
    source_name="main.py",
    # py_compile only checks syntax, which turns a typo into CE instead of RE
    compile_argv=("python3", "-m", "py_compile", "main.py"),
    run_argv=("python3", "main.py"),
    tl_multiplier=3.0,
    ml_multiplier=2.0,
)

_REGISTRY: dict[str, Language] = {lang.id: lang for lang in (CPP, PYTHON)}


def get(language_id: str) -> Language:
    """Look up a language, raising if it is not supported."""
    try:
        return _REGISTRY[language_id]
    except KeyError:
        raise UnknownLanguage(language_id) from None


def all_languages() -> tuple[Language, ...]:
    return tuple(_REGISTRY.values())


def register(language: Language) -> None:
    """Add a language at runtime, so judging code never changes for a new one."""
    if language.id in _REGISTRY:
        raise ValueError(f"language already registered: {language.id}")
    _REGISTRY[language.id] = language


class UnknownLanguage(KeyError):
    """Asked for a language we do not support."""

    def __init__(self, language_id: str) -> None:
        super().__init__(language_id)
        self.language_id = language_id

    def __str__(self) -> str:
        return f"unsupported language: {self.language_id}"
