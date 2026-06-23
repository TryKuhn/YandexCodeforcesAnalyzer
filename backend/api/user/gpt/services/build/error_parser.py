"""Figure out which file a Polygon build error came from.

The build retry loop needs to know *which* file_type to hand the fixer. We try
cheap deterministic signals first (known filenames in the log, ``path:line:
error`` markers, testlib phase markers) and fall back to a Haiku classifier
only when the regexes are inconclusive.
"""
import logging
import re

from api.user.gpt.services.ai_file_helpers import FILE_NAME_MAP
from api.user.gpt.services.llm.client import llm
from api.user.gpt.services.llm.models import ROUTER_MODEL

logger = logging.getLogger(__name__)

_FILENAME_TO_TYPE: dict[str, str] = {}
for _ft, _fn in FILE_NAME_MAP.items():
    _FILENAME_TO_TYPE.setdefault(_fn, _ft)

_PHASE_MARKERS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"validat", re.I), "validator"),
    (re.compile(r"generator (crash|fail|return)", re.I), "generator"),
    (re.compile(r"\bgenerator\b", re.I), "generator"),
    (re.compile(r"interactor", re.I), "interactor"),
    (re.compile(r"checker", re.I), "checker"),
    (re.compile(r"\bscript\b", re.I), "script"),
    (re.compile(r"wrong answer|main (correct )?solution|judgement", re.I), "solution_cpp"),
]


def parse_offending_file(log: str, applicable: list[str] | None = None) -> str | None:
    """Return the offending file_type from a build log, or None if unclear.

    Tries, in order: explicit filename mentions, a ``path:line:`` error marker
    (mapped via basename), then testlib/Polygon phase markers. ``applicable``
    restricts the answer to file types valid for the problem type (e.g. a
    regular problem has no ``scorer``); when given, a guess outside the set is
    rejected so the caller can fall back to the LLM classifier.
    """
    if not log:
        return None

    def _ok(ft: str | None) -> str | None:
        if ft and (applicable is None or ft in applicable):
            return ft
        return None

    for filename, file_type in _FILENAME_TO_TYPE.items():
        if filename in log:
            hit = _ok(file_type)
            if hit:
                return hit

    m = re.search(r"([\w./-]+?\.(?:cpp|py|txt)):\d+", log)
    if m:
        basename = m.group(1).split("/")[-1]
        hit = _ok(_FILENAME_TO_TYPE.get(basename))
        if hit:
            return hit

    for pattern, file_type in _PHASE_MARKERS:
        if pattern.search(log):
            hit = _ok(file_type)
            if hit:
                return hit

    return None


async def classify_offending_file(
    log: str, applicable: list[str]
) -> str | None:
    """Haiku fallback: pick the most likely offending file_type from the set."""
    if not log or not applicable:
        return None
    system = (
        "Ты анализируешь лог сборки задачи в Polygon. Определи, в каком файле "
        "произошла ошибка. Ответь строго JSON-объектом {\"file_type\": <one of "
        f"{applicable} or null>}}. Никакого текста кроме JSON."
    )
    try:
        result = await llm.ask(
            ROUTER_MODEL,
            [
                {"role": "system", "content": system},
                {"role": "user", "content": f"Лог сборки:\n{log[:4000]}"},
            ],
            json_mode=True,
        )
        ft = result.get("file_type")
        return ft if ft in applicable else None
    except Exception as e:
        logger.warning(f"classify_offending_file failed: {e}")
        return None


async def resolve_offending_file(
    log: str, applicable: list[str]
) -> str | None:
    """Deterministic parse first, Haiku classifier as fallback."""
    guess = parse_offending_file(log, applicable)
    if guess:
        return guess
    return await classify_offending_file(log, applicable)
