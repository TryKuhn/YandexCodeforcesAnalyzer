"""The tagged output protocol for edits.

Models return code and LaTeX, both full of quotes and backslashes, so instead
of JSON (where one bad escape loses the whole answer) edits come as tagged
blocks whose bodies are taken verbatim::

    <reply>Markdown for the user</reply>
    <file role="generator" name="gen1.cpp">...source...</file>
    <file role="solution" name="wa.cpp" tag="WA">...</file>
    <statement lang="russian" field="legend">...LaTeX...</statement>
    <script>...FreeMarker...</script>
    <limits time_limit="2000" memory_limit="256"/>
    <tags>dp, greedy</tags>
    <checker standard="std::ncmp.cpp"/>
    <sample>input of a sample test</sample>
    <groups>{"groups": [...]}</groups>

Unknown tags and text between blocks are ignored.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from authoring.llm.client import LLMError, strip_fences

# what a model may change; the router restricts an edit to a subset of these
TARGETS = (
    "statement",
    "solution",
    "validator",
    "checker",
    "interactor",
    "generator",
    "script",
    "limits",
    "tags",
    "groups",
    "samples",
)

FILE_ROLES = ("solution", "validator", "checker", "interactor", "generator", "source")
STATEMENT_FIELDS = ("name", "legend", "input", "output", "scoring", "interaction", "notes", "tutorial")
SOLUTION_TAGS = ("MA", "OK", "RJ", "TL", "TO", "TM", "WA", "PE", "ML", "NR", "RE")

_TAGS = "reply|file|statement|script|limits|tags|checker|sample|groups"
_BLOCK_RE = re.compile(
    rf"<(?P<tag>{_TAGS})(?P<attrs>(?:\s+[\w-]+\s*=\s*(?:\"[^\"]*\"|'[^']*'))*)\s*"
    rf"(?:/>|>(?P<body>.*?)</(?P=tag)\s*>)",
    re.DOTALL,
)
_ATTR_RE = re.compile(r"([\w-]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)')")
_OPEN_RE = re.compile(rf"<(?P<tag>{_TAGS})[\s>]")
_NAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.+-]{0,63}$")
# Polygon finds testlib.h only with the quoted form
_TESTLIB_INCLUDE_RE = re.compile(r"#include\s*<\s*testlib\.h\s*>")


@dataclass
class FileEdit:
    role: str
    name: str
    content: str
    tag: str | None = None  # solutions only

    @property
    def target(self) -> str:
        return "generator" if self.role == "source" else self.role


@dataclass
class StatementEdit:
    lang: str
    field: str
    content: str
    target: str = "statement"


@dataclass
class ScriptEdit:
    content: str
    target: str = "script"


@dataclass
class LimitsEdit:
    time_limit: int | None = None
    memory_limit: int | None = None
    target: str = "limits"


@dataclass
class TagsEdit:
    tags: list[str]
    target: str = "tags"


@dataclass
class StandardChecker:
    name: str
    target: str = "checker"


@dataclass
class SampleEdit:
    input: str
    target: str = "samples"


@dataclass
class GroupsEdit:
    plan: dict
    target: str = "groups"


Edit = FileEdit | StatementEdit | ScriptEdit | LimitsEdit | TagsEdit | StandardChecker | SampleEdit | GroupsEdit


@dataclass
class Parsed:
    reply: str = ""
    edits: list[Edit] = field(default_factory=list)
    # problems with individual blocks; reported to the user, never fatal
    warnings: list[str] = field(default_factory=list)


def _body(text: str | None) -> str:
    """Block body without the surrounding newlines (and a stray code fence)."""
    if text is None:
        return ""
    text = text.strip("\r\n")
    if text.lstrip().startswith("```"):
        text = strip_fences(text)
    return text


def _int(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    try:
        return int(float(value.strip()))
    except (ValueError, OverflowError):
        return None


def parse(text: str) -> Parsed:
    """Parse the tagged blocks of a model answer."""
    result = Parsed()
    replies: list[str] = []
    for m in _BLOCK_RE.finditer(text):
        tag = m.group("tag")
        attrs = {k: v1 or v2 for k, v1, v2 in _ATTR_RE.findall(m.group("attrs") or "")}
        body = _body(m.group("body"))
        if tag == "reply":
            replies.append(body.strip())
        elif tag == "file":
            role = attrs.get("role", "").strip().lower()
            name = attrs.get("name", "").strip()
            if role not in FILE_ROLES:
                result.warnings.append(f"файл {name or '?'}: неизвестная роль {role!r}")
                continue
            if not _NAME_RE.match(name):
                result.warnings.append(f"недопустимое имя файла {name!r}")
                continue
            if not body.strip():
                result.warnings.append(f"файл {name}: пустое содержимое")
                continue
            tag_value = (attrs.get("tag") or "").strip().upper() or None
            if role == "solution" and tag_value and tag_value not in SOLUTION_TAGS:
                result.warnings.append(f"решение {name}: неизвестный тег {tag_value}")
                tag_value = None
            body = _TESTLIB_INCLUDE_RE.sub('#include "testlib.h"', body)
            result.edits.append(FileEdit(role, name, body + "\n", tag_value))
        elif tag == "statement":
            fld = attrs.get("field", "").strip().lower()
            if fld not in STATEMENT_FIELDS:
                result.warnings.append(f"условие: неизвестное поле {fld!r}")
                continue
            lang = attrs.get("lang", "russian").strip().lower() or "russian"
            result.edits.append(StatementEdit(lang, fld, body.strip()))
        elif tag == "script":
            if body.strip():
                result.edits.append(ScriptEdit(body.strip() + "\n"))
        elif tag == "limits":
            tl, ml = _int(attrs.get("time_limit")), _int(attrs.get("memory_limit"))
            if tl is not None or ml is not None:
                result.edits.append(LimitsEdit(tl, ml))
        elif tag == "tags":
            tags = [t.strip() for t in re.split(r"[,\n]", body) if t.strip()]
            result.edits.append(TagsEdit(tags))
        elif tag == "checker":
            name = attrs.get("standard", "").strip()
            if name:
                if not name.startswith("std::"):
                    name = f"std::{name}"
                if not name.endswith(".cpp"):
                    name += ".cpp"
                result.edits.append(StandardChecker(name))
        elif tag == "sample":
            if body.strip():
                result.edits.append(SampleEdit(body.strip("\r\n") + "\n"))
        elif tag == "groups":
            try:
                plan = json.loads(strip_fences(body))
            except ValueError as e:
                result.warnings.append(f"план групп: некорректный JSON ({e})")
                continue
            if isinstance(plan, dict):
                result.edits.append(GroupsEdit(plan))
    opened = sum(1 for m in _OPEN_RE.finditer(text) if m.group("tag") != "limits")
    closed = sum(1 for m in _BLOCK_RE.finditer(text) if m.group("tag") != "limits")
    if opened > closed:
        result.warnings.append("часть ответа модели оборвана или не разобрана — эти изменения не применены")
    result.reply = "\n\n".join(r for r in replies if r)
    if not result.reply and not result.edits:
        # a model that ignored the protocol: its whole answer is the reply
        result.reply = text.strip()
    return result


def single_file(text: str, *, role: str) -> FileEdit:
    """The one ``<file>`` of an answer (or the whole answer as raw source)."""
    parsed = parse(text)
    files = [e for e in parsed.edits if isinstance(e, FileEdit)]
    if files:
        return files[0]
    source = _TESTLIB_INCLUDE_RE.sub('#include "testlib.h"', strip_fences(text))
    if not source.strip():
        raise LLMError(f"Модель не вернула код ({role})")
    return FileEdit(role, "", source.rstrip() + "\n")
