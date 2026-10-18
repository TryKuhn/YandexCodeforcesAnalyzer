"""Builders for Polygon packages and an in-memory ejudge host."""
from __future__ import annotations

import io
import posixpath
import re
import zipfile

from api.user.ejudge.remote import CommandResult

SERVE_CFG = """# -*- coding: utf-8 -*-
contest_time = 300
score_system = olympiad # olympiad scoring
advanced_layout

[language]
id = 3
short_name = "g++"

[problem]
abstract
short_name = "Generic"
use_stdin
use_stdout

[problem]
id = 1
super = "Generic"
short_name = "A"
long_name = "Old problem"
internal_name = "old"
"""


def package_zip(
    tests: list[dict],
    groups: list[dict] | None = None,
    *,
    name: str = "a-plus-b",
    interactor: bool = False,
    answers: bool = True,
    input_file: str = "",
    time_limit: int = 1000,
    memory: int = 256 * 1024 * 1024,
) -> bytes:
    """tests: [{"group": "1", "points": 30, "sample": True}, ...]"""
    test_xml = []
    for t in tests:
        attrs = ['method="manual"']
        if t.get("group") is not None:
            attrs.append(f'group="{t["group"]}"')
        if t.get("points") is not None:
            attrs.append(f'points="{float(t["points"])}"')
        if t.get("sample"):
            attrs.append('sample="true"')
        test_xml.append(f"<test {' '.join(attrs)}/>")
    groups_xml = ""
    if groups:
        rows = []
        for g in groups:
            deps = "".join(f'<dependency group="{d}"/>' for d in g.get("deps", []))
            rows.append(
                f'<group feedback-policy="{g.get("feedback", "icpc")}" name="{g["name"]}" '
                f'points-policy="{g.get("policy", "complete-group")}">'
                + (f"<dependencies>{deps}</dependencies>" if deps else "") + "</group>"
            )
        groups_xml = f"<groups>{''.join(rows)}</groups>"
    interactor_xml = '<interactor><source path="files/interactor.cpp" type="cpp.g++17"/></interactor>' \
        if interactor else ""
    xml = f"""<?xml version="1.0" encoding="utf-8" standalone="no"?>
<problem revision="7" short-name="{name}" url="https://polygon.codeforces.com/p/u/{name}">
  <names><name language="russian" value="Сумма"/><name language="english" value="Sum"/></names>
  <judging input-file="{input_file}" output-file="">
    <testset name="tests">
      <time-limit>{time_limit}</time-limit>
      <memory-limit>{memory}</memory-limit>
      <test-count>{len(tests)}</test-count>
      <input-path-pattern>tests/%02d</input-path-pattern>
      <answer-path-pattern>tests/%02d.a</answer-path-pattern>
      <tests>{''.join(test_xml)}</tests>
      {groups_xml}
    </testset>
  </judging>
  <files><resources><file path="files/testlib.h" type="h.g++"/><file path="files/olymp.sty"/></resources></files>
  <assets>
    <checker name="std::ncmp.cpp" type="testlib"><source path="files/check.cpp" type="cpp.g++17"/></checker>
    {interactor_xml}
    <solutions><solution tag="main"><source path="solutions/main.cpp" type="cpp.g++17"/></solution></solutions>
  </assets>
</problem>"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("problem.xml", xml)
        zf.writestr("files/testlib.h", "// testlib\n")
        zf.writestr("files/olymp.sty", "%")
        zf.writestr("files/check.cpp", '#include "testlib.h"\nint main(){}\n')
        if interactor:
            zf.writestr("files/interactor.cpp", "int main(){}\n")
        for i in range(1, len(tests) + 1):
            zf.writestr(f"tests/{i:02d}", f"input {i}\n")
            if answers:
                zf.writestr(f"tests/{i:02d}.a", f"answer {i}\n")
    return buf.getvalue()


class FakeHost:
    """An in-memory remote filesystem with a tiny shell (mv / cp / cd&&g++ / rm / chmod / test)."""

    def __init__(self, files: dict[str, bytes] | None = None, *, fail_compile: str | None = None):
        self.files: dict[str, bytes] = dict(files or {})
        self.commands: list[str] = []
        self.fail_compile = fail_compile
        self.entered = 0
        self.reads: list[str] = []
        self.after_read: dict[int, object] = {}  # n-th read (1-based) -> callable(host), simulates edits
        self.fail_rename = False

    # async context manager, like SSHHost
    def __call__(self, settings) -> FakeHost:  # host_factory(settings)
        return self

    async def __aenter__(self) -> FakeHost:
        self.entered += 1
        return self

    async def __aexit__(self, *exc) -> None:
        return None

    async def read_text(self, path: str) -> str:
        from api.user.ejudge.common import EjudgeError
        if path not in self.files:
            raise EjudgeError(f"не удалось прочитать {path}: no such file")
        self.reads.append(path)
        text = self.files[path].decode()
        hook = self.after_read.get(len(self.reads))
        if hook is not None:
            hook(self)  # type: ignore[operator]
        return text

    async def rename(self, src: str, dst: str) -> None:
        from api.user.ejudge.common import EjudgeError
        if self.fail_rename:
            raise EjudgeError(f"не удалось переименовать {src} в {dst}: permission denied")
        self.files[dst] = self.files.pop(src)

    async def write_files(self, base: str, files: dict[str, bytes]) -> None:
        for rel, content in files.items():
            self.files[posixpath.join(base, rel)] = content

    async def write_text(self, path: str, text: str) -> None:
        self.files[path] = text.encode()

    def _move(self, src: str, dst: str) -> None:
        moved = {k: v for k, v in self.files.items() if k == src or k.startswith(src + "/")}
        for k in moved:
            del self.files[k]
            self.files[dst + k[len(src):]] = moved[k]

    async def run(self, command: str) -> CommandResult:
        self.commands.append(command)
        unq = command.replace("'", "")
        m = re.match(r"^cd (\S+) && .* -o (\S+) (\S+)$", unq)
        if m:
            base, exe, src = m.groups()
            if self.fail_compile and src == self.fail_compile:
                return CommandResult(1, "", f"{src}: error: expected ';'")
            assert posixpath.join(base, src) in self.files, f"missing {src}"
            self.files[posixpath.join(base, exe)] = b"ELF"
            return CommandResult(0, "", "")
        m = re.match(r"^if \[ -e (\S+) \]; then mv (\S+) (\S+); fi && mv (\S+) (\S+) && chmod -R a\+rX (\S+)$", unq)
        if m:
            final, _, backup, staging, _, _ = m.groups()
            if any(k.startswith(final + "/") for k in self.files):
                self._move(final, backup)
            self._move(staging, final)
            return CommandResult(0, "", "")
        m = re.match(r"^rm -rf (\S+) && if \[ -e (\S+) \]; then mv (\S+) (\S+); fi$", unq)
        if m:
            final, backup = m.group(1), m.group(2)
            for k in [k for k in self.files if k.startswith(final + "/")]:
                del self.files[k]
            if any(k.startswith(backup + "/") for k in self.files):
                self._move(backup, final)
            return CommandResult(0, "", "")
        m = re.match(r"^cp (?:-p )?(\S+) (\S+)$", unq)
        if m:
            src, dst = m.groups()
            if src not in self.files:
                return CommandResult(1, "", f"cp: {src}: No such file")
            self.files[dst] = self.files[src]
            return CommandResult(0, "", "")
        m = re.match(r"^rm -rf (\S+)$", unq)
        if m:
            target = m.group(1)
            for k in [k for k in self.files if k == target or k.startswith(target + "/")]:
                del self.files[k]
            return CommandResult(0, "", "")
        raise AssertionError(f"unexpected command {command}")

    def tree(self, prefix: str) -> list[str]:
        return sorted(k[len(prefix):].lstrip("/") for k in self.files if k.startswith(prefix + "/"))
