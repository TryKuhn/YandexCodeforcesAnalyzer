"""Reading and editing ejudge's ``serve.cfg`` without disturbing the rest of it.

The file is a list of sections (``[problem]``, ``[language]``, ...) after a
global part. Only one ``[problem]`` block is replaced or appended; every other
line (comments included) is kept as is.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

_SECTION_RE = re.compile(r"^\s*\[\s*([A-Za-z_]+)\s*\]\s*(#.*)?$")
_KV_RE = re.compile(r"^\s*([A-Za-z0-9_]+)\s*(?:=\s*(.*?))?\s*$")


class Unquoted(str):
    """A value written without quotes (``256M``)."""


def unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


def render_value(value: object) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f"{value:g}" if isinstance(value, float) else str(value)
    if isinstance(value, Unquoted):
        return str(value)
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def render_section(name: str, values: dict[str, object]) -> list[str]:
    lines = [f"[{name}]"]
    for key, value in values.items():
        if value is None:
            continue
        lines.append(f"{key} = {render_value(value)}")
    return lines


@dataclass
class Section:
    name: str  # "" for the global part
    start: int  # first line (the header for named sections)
    end: int  # one past the last line
    values: dict[str, str] = field(default_factory=dict)


def _strip_comment(line: str) -> str:
    out, quoted = [], False
    for ch in line:
        if ch == '"':
            quoted = not quoted
        if ch == "#" and not quoted:
            break
        out.append(ch)
    return "".join(out)


class ServeCfg:
    def __init__(self, text: str):
        self.newline = "\r\n" if "\r\n" in text else "\n"
        self.lines = text.splitlines()
        self.sections = self._parse()

    def _parse(self) -> list[Section]:
        sections = [Section("", 0, len(self.lines))]
        for i, raw in enumerate(self.lines):
            m = _SECTION_RE.match(raw)
            if m:
                sections[-1].end = i
                sections.append(Section(m.group(1), i, len(self.lines)))
                continue
            line = _strip_comment(raw).strip()
            if not line:
                continue
            kv = _KV_RE.match(line)
            if kv:
                sections[-1].values[kv.group(1)] = unquote(kv.group(2) or "1")
        return sections

    # ------------------------------------------------------------------ reading
    @property
    def globals(self) -> dict[str, str]:
        return self.sections[0].values

    @property
    def score_system(self) -> str:
        return (self.globals.get("score_system") or "acm").strip().lower()

    @property
    def advanced_layout(self) -> bool:
        return self.globals.get("advanced_layout", "0") not in ("0", "")

    def problems(self) -> list[Section]:
        return [s for s in self.sections if s.name == "problem"]

    def concrete_problems(self) -> list[Section]:
        return [s for s in self.problems() if s.values.get("abstract", "0") in ("0", "")]

    def abstract_problems(self) -> list[Section]:
        return [s for s in self.problems() if s.values.get("abstract", "0") not in ("0", "")]

    def find_problem(self, *, extid: str | None = None, problem_id: int | None = None) -> Section | None:
        """By extid first, then by an explicit id."""
        for s in self.concrete_problems():
            if extid and s.values.get("extid") == extid:
                return s
        for s in self.concrete_problems():
            if problem_id is not None and s.values.get("id") == str(problem_id):
                return s
        return None

    def free_internal_name(self, wanted: str, exclude: Section | None = None) -> str:
        used = {s.values.get("internal_name") for s in self.problems()
                if exclude is None or s.start != exclude.start}
        name, i = wanted, 2
        while name in used:
            name, i = f"{wanted}-{i}", i + 1
        return name

    def next_problem_id(self) -> int:
        ids = [int(s.values["id"]) for s in self.concrete_problems() if s.values.get("id", "").isdigit()]
        return max(ids, default=0) + 1

    def free_short_name(self, wanted: str | None = None, exclude: Section | None = None) -> str:
        used = {s.values.get("short_name") for s in self.problems()
                if exclude is None or s.start != exclude.start}
        if wanted and wanted not in used:
            return wanted
        for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            if ch not in used:
                return ch
        i = 1
        while f"P{i}" in used:
            i += 1
        return f"P{i}"

    # ------------------------------------------------------------------ editing
    def upsert_problem(
        self, existing: Section | None, values: dict[str, object], managed: Iterable[str] = ()
    ) -> None:
        """Append a new block, or merge ``values`` into ``existing``.

        In an existing block the keys from ``values`` are rewritten in place,
        keys from ``managed`` that are no longer wanted (``time_limit`` after a
        switch to ``time_limit_millis``, ``valuer_cmd`` in an ACM contest) are
        dropped, and everything else (other keys, comments) is kept.
        """
        if existing is None:
            if self.lines and self.lines[-1].strip():
                self.lines.append("")
            self.lines.extend(render_section("problem", values))
            self.sections = self._parse()
            return

        wanted = {k: v for k, v in values.items() if v is not None}
        drop = set(managed) - set(wanted)
        body: list[str] = []
        written: set[str] = set()
        for raw in self.lines[existing.start + 1:existing.end]:
            kv = _KV_RE.match(_strip_comment(raw).strip())
            key = kv.group(1) if kv and _strip_comment(raw).strip() else None
            if key in wanted:
                if key not in written:
                    body.append(f"{key} = {render_value(wanted[key])}")
                    written.add(key)
                continue
            if key in drop:
                continue
            body.append(raw)
        # new keys go after the last non-blank line, before the separating blank lines
        tail = len(body)
        while tail > 0 and not body[tail - 1].strip():
            tail -= 1
        body[tail:tail] = [f"{k} = {render_value(v)}" for k, v in wanted.items() if k not in written]
        self.lines[existing.start + 1:existing.end] = body
        self.sections = self._parse()

    def set_global(self, key: str, value: object) -> None:
        rendered = f"{key} = {render_value(value)}"
        glob = self.sections[0]
        for i in range(glob.start, glob.end):
            kv = _KV_RE.match(_strip_comment(self.lines[i]).strip())
            if kv and kv.group(1) == key:
                self.lines[i] = rendered
                break
        else:
            self.lines.insert(glob.end, rendered)
        self.sections = self._parse()

    def text(self) -> str:
        return self.newline.join(self.lines) + self.newline


def summary(cfg: ServeCfg, keys: Iterable[str] = ("id", "short_name", "long_name", "internal_name", "extid")) -> list[dict]:
    return [{k: s.values.get(k) for k in keys} for s in cfg.concrete_problems()]
