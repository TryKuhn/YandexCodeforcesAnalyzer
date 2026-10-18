"""Test doubles: an in-memory backend with Polygon problems and a scripted LLM."""
from __future__ import annotations

import json
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import unquote

import httpx

from authoring.llm.client import Completion, LLMError, Msg


# --------------------------------------------------------------------------- Polygon
@dataclass
class FakeProblem:
    id: int
    name: str
    info: dict = field(default_factory=lambda: {
        "inputFile": "stdin", "outputFile": "stdout", "interactive": False,
        "timeLimit": 1000, "memoryLimit": 256, "wellFormed": False,
    })
    statements: dict = field(default_factory=dict)
    tags: list = field(default_factory=list)
    files: dict = field(default_factory=dict)       # "type/name" -> {content, mtime}
    solutions: dict = field(default_factory=dict)   # name -> {content, tag, mtime}
    checker: str = ""
    validator: str = ""
    interactor: str = ""
    script: str = ""
    tests: dict = field(default_factory=dict)       # index -> test dict
    groups_enabled: bool = False
    points_enabled: bool = False
    groups: dict = field(default_factory=dict)      # name -> {pointsPolicy, feedbackPolicy, dependencies}
    packages: list = field(default_factory=list)
    commits: list = field(default_factory=list)


_LIST_RE = re.compile(r"<#list\s+(\d+)\.\.(\d+)\s+as\s+(\w+)>(.*?)</#list>", re.DOTALL)
_EXPR_RE = re.compile(r"\$\{\s*(\w+)\s*\+\s*(\d+)\s*\}|\$\{\s*(\w+)\s*\}")


def expand_freemarker(script: str) -> list[str]:
    """Tiny FreeMarker subset: <#list a..b as i>, ${i}, ${i + k}, <#-- comments -->."""
    script = re.sub(r"<#--.*?-->", "", script, flags=re.DOTALL)

    def expand_list(m: re.Match) -> str:
        lo, hi, var, body = int(m.group(1)), int(m.group(2)), m.group(3), m.group(4)
        out = []
        for i in range(lo, hi + 1):
            def repl(e: re.Match, i: int = i) -> str:
                if e.group(1) == var:
                    return str(i + int(e.group(2)))
                if e.group(3) == var:
                    return str(i)
                return e.group(0)
            out.append(_EXPR_RE.sub(repl, body))
        return "".join(out)

    script = _LIST_RE.sub(expand_list, script)
    return [line.strip() for line in script.splitlines() if line.strip().endswith("> $")]


class FakeBackend:
    """Implements the subset of /api/polygon the service uses."""

    def __init__(self) -> None:
        self.problems: dict[int, FakeProblem] = {}
        self.next_id = 1000
        self.clock = 1_700_000_000
        self.calls: list[tuple[str, str]] = []
        self.build_outcomes: list[tuple[str, str]] = []  # (state, comment) per build
        self.fail_paths: dict[str, tuple[int, str]] = {}
        self.users: set[int] = set()

    def tick(self) -> int:
        self.clock += 1
        return self.clock

    def add_problem(self, name: str = "test-problem", **kwargs: Any) -> FakeProblem:
        self.next_id += 1
        problem = FakeProblem(self.next_id, name, **kwargs)
        self.problems[problem.id] = problem
        return problem

    def put_file(self, problem: FakeProblem, file_type: str, name: str, content: str) -> None:
        problem.files[f"{file_type}/{name}"] = {"content": content, "mtime": self.tick()}

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handle)

    # ------------------------------------------------------------------ dispatch
    def handle(self, request: httpx.Request) -> httpx.Response:
        path = unquote(request.url.path)
        assert path.startswith("/api/"), path
        path = path[len("/api"):]
        self.calls.append((request.method, path))
        for prefix, (status, detail) in self.fail_paths.items():
            if path.startswith(prefix):
                return httpx.Response(status, json={"detail": detail})
        body = json.loads(request.content) if request.content else None
        params = dict(request.url.params)
        try:
            result = self.route(request.method, path, body, params)
        except KeyError as e:
            return httpx.Response(404, json={"detail": f"not found: {e}"})
        except ValueError as e:
            return httpx.Response(400, json={"detail": str(e)})
        if isinstance(result, httpx.Response):
            return result
        return httpx.Response(200, json=result)

    def route(self, method: str, path: str, body: Any, params: dict) -> Any:  # noqa: C901
        if method == "POST" and path == "/polygon/problems/":
            problem = self.add_problem(body["name"])
            return {"polygon_id": problem.id, "name": problem.name}
        m = re.match(r"^/polygon/problems/(\d+)(/.*)?$", path)
        if not m:
            raise KeyError(path)
        p = self.problems[int(m.group(1))]
        sub = m.group(2) or ""

        if sub == "/info":
            if method == "GET":
                return dict(p.info)
            mapping = {"time_limit": "timeLimit", "memory_limit": "memoryLimit", "interactive": "interactive",
                       "input_file": "inputFile", "output_file": "outputFile"}
            for k, v in body.items():
                p.info[mapping[k]] = v
            return {"ok": True}
        if sub == "/statement":
            if method == "GET":
                return p.statements
            lang = body.pop("lang")
            current = p.statements.setdefault(lang, {})
            for k in ("name", "legend", "input", "output", "scoring", "interaction", "notes", "tutorial"):
                if k in ("legend", "input", "output", "name"):
                    current[k] = body.get(k, "")
                elif body.get(k) is not None:
                    current[k] = body[k]
            return {"ok": True}
        if sub == "/tags":
            if method == "GET":
                return {"tags": p.tags}
            p.tags = list(body["tags"])
            return {"ok": True}
        if sub == "/files" and method == "GET":
            out: dict = {"resourceFiles": [], "sourceFiles": [], "auxFiles": []}
            for key, f in p.files.items():
                ftype, name = key.split("/", 1)
                out[f"{ftype}Files"].append({"name": name, "modificationTimeSeconds": f["mtime"],
                                             "length": len(f["content"]), "sourceType": "cpp.g++17"})
            out["solutions"] = [
                {"name": n, "tag": s["tag"], "modificationTimeSeconds": s["mtime"], "length": len(s["content"]),
                 "sourceType": "cpp.g++17"}
                for n, s in p.solutions.items()
            ]
            return out
        if sub == "/files" and method == "POST":
            self.put_file(p, body["type"], body["name"], body["content"])
            return {"ok": True}
        if sub == "/files/content":
            return {"content": p.files[f"{params['type']}/{params['name']}"]["content"]}
        m2 = re.match(r"^/solutions/(.+)/content$", sub)
        if m2:
            return {"content": p.solutions[m2.group(1)]["content"]}
        if sub == "/solutions" and method == "POST":
            if body.get("tag") == "MA" and any(
                s["tag"] == "MA" and n != body["name"] for n, s in p.solutions.items()
            ):
                raise ValueError("only one main solution")
            p.solutions[body["name"]] = {"content": body["content"], "tag": body.get("tag") or "OK",
                                         "mtime": self.tick()}
            return {"ok": True}
        for part in ("checker", "validator", "interactor"):
            if sub == f"/{part}":
                if method == "GET":
                    return {part: getattr(p, part)}
                if body.get("content") is not None:
                    self.put_file(p, "source", body["name"], body["content"])
                elif not body["name"].startswith("std::") and f"source/{body['name']}" not in p.files:
                    raise ValueError(f"no file {body['name']}")
                setattr(p, part, body["name"])
                return {"ok": True}
        if sub == "/script/tests":
            if method == "GET":
                return {"content": p.script}
            if method == "DELETE":
                p.script = ""
                p.tests = {i: t for i, t in p.tests.items() if t["manual"]}
                return {"ok": True}
            self._save_script(p, body["source"])
            return {"ok": True}
        if sub == "/tests/tests" and method == "GET":
            return [dict(t) for _, t in sorted(p.tests.items())]
        if sub == "/tests/tests" and method == "POST":
            index = body["test_index"]
            test = p.tests.get(index)
            if test is None:
                if body.get("test_input") is None:
                    raise ValueError("testInput required for a new test")
                test = {"index": index, "manual": True, "input": body["test_input"], "group": None,
                        "points": None, "useInStatements": False, "scriptLine": None, "description": None}
                p.tests[index] = test
            if body.get("test_input") is not None:
                if not test["manual"]:
                    raise ValueError("generated test input cannot be changed")
                test["input"] = body["test_input"]
            if body.get("test_points") is not None:
                if not p.points_enabled:
                    raise ValueError("points are disabled")
                test["points"] = body["test_points"]
            if body.get("test_group") is not None:
                test["group"] = body["test_group"]
            if body.get("test_use_in_statements") is not None:
                test["useInStatements"] = body["test_use_in_statements"]
            return {"ok": True}
        if sub == "/tests/tests/group":
            if not p.groups_enabled:
                raise ValueError("groups are disabled")
            for i in body["test_indices"]:
                p.tests[i]["group"] = body["test_group"]
            p.groups.setdefault(body["test_group"], {"pointsPolicy": "EACH_TEST", "feedbackPolicy": "COMPLETE",
                                                     "dependencies": []})
            return {"ok": True}
        m3 = re.match(r"^/tests/tests/(\d+)/input$", sub)
        if m3:
            test = p.tests[int(m3.group(1))]
            return {"content": test.get("input") or f"generated by {test.get('scriptLine')}"}
        if sub == "/settings/enable-groups":
            p.groups_enabled = body["enable"]
            if not body["enable"]:
                p.groups = {}
                for t in p.tests.values():
                    t["group"] = None
            return {"ok": True}
        if sub == "/settings/enable-points":
            p.points_enabled = body["enable"]
            return {"ok": True}
        if sub == "/groups/tests":
            if not p.groups_enabled:
                return httpx.Response(400, json={"detail": "groups are disabled"})
            return [{"name": n, **g} for n, g in p.groups.items()]
        m4 = re.match(r"^/groups/tests/(.+)$", sub)
        if m4 and method == "PUT":
            name = m4.group(1)
            if name not in p.groups:
                raise ValueError(f"no group {name}")
            for dep in body.get("dependencies") or []:
                if dep not in p.groups:
                    raise ValueError(f"unknown dependency {dep}")
            p.groups[name] = {"pointsPolicy": body["points_policy"], "feedbackPolicy": body["feedback_policy"],
                              "dependencies": list(body.get("dependencies") or [])}
            return {"ok": True}
        if sub == "/packages" and method == "GET":
            for pkg in p.packages:
                if pkg["state"] in ("PENDING", "RUNNING"):
                    state, comment = self.build_outcomes.pop(0) if self.build_outcomes else ("READY", "")
                    pkg["state"], pkg["comment"] = state, comment
            return [dict(x) for x in p.packages]
        if sub == "/packages/build":
            p.commits.append("before build")
            p.packages.append({"id": len(p.packages) + 1, "revision": len(p.commits), "state": "PENDING",
                               "comment": "", "type": "standard", "creationTimeSeconds": self.tick()})
            return {"status": "building"}
        if sub == "/commit":
            p.commits.append(body.get("message") or "")
            return {"ok": True}
        if sub == "/cautions":
            return []
        raise KeyError(f"{method} {sub}")

    def _save_script(self, p: FakeProblem, source: str) -> None:
        p.script = source
        p.tests = {i: t for i, t in p.tests.items() if t["manual"]}
        index = 1
        for line in expand_freemarker(source):
            while index in p.tests:
                index += 1
            p.tests[index] = {"index": index, "manual": False, "input": None, "group": None, "points": None,
                              "useInStatements": False, "scriptLine": line[:-len("> $")].strip(),
                              "description": None}
        if len(set(t["scriptLine"] for t in p.tests.values() if not t["manual"])) != sum(
            1 for t in p.tests.values() if not t["manual"]
        ):
            raise ValueError("duplicate script lines")


# --------------------------------------------------------------------------- LLM
Responder = Callable[[str, list[Msg]], str]


@dataclass
class Call:
    model: str
    messages: list[Msg]
    json_mode: bool

    @property
    def system(self) -> str:
        return "\n".join(p.text for m in self.messages if m.role == "system" for p in m.parts)

    @property
    def user(self) -> str:
        return "\n".join(p.text for m in self.messages if m.role == "user" for p in m.parts)


class FakeLLM:
    """Answers by the first rule whose marker occurs in the system prompt."""

    def __init__(self) -> None:
        self.rules: list[tuple[str, Responder | str]] = []
        self.calls: list[Call] = []
        self.blocked: set[str] = set()

    def on(self, marker: str, answer: Responder | str) -> FakeLLM:
        self.rules.append((marker, answer))
        return self

    async def complete(self, model: str, messages: Sequence[Msg], *, max_tokens: int | None = None,
                       json_mode: bool = False) -> Completion:
        call = Call(model, list(messages), json_mode)
        self.calls.append(call)
        if model in self.blocked:
            raise LLMError("blocked", status=403, fallback_ok=True)
        for marker, answer in self.rules:
            if marker in call.system or marker in call.user:
                text = answer(model, list(messages)) if callable(answer) else answer
                return Completion(text=text, model=model)
        raise AssertionError(f"no fake answer for system prompt: {call.system[:200]}")

    async def complete_any(self, models: Sequence[str], messages: Sequence[Msg], *, max_tokens: int | None = None,
                           json_mode: bool = False) -> Completion:
        last: LLMError | None = None
        for model in models:
            try:
                return await self.complete(model, messages, max_tokens=max_tokens, json_mode=json_mode)
            except LLMError as e:
                last = e
                if not e.fallback_ok:
                    raise
        assert last is not None
        raise last

    def calls_with(self, marker: str) -> list[Call]:
        return [c for c in self.calls if marker in c.system or marker in c.user]
