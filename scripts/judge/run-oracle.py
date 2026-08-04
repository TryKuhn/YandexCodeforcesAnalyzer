#!/usr/bin/env python3
"""Judge every oracle solution and check it gets the verdict its tag claims (YCA-407).

Needs the judge service running:
    docker compose -f docker-compose.dev.yml up -d --build judge
    ./scripts/judge/run-oracle.py
"""
import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

JUDGE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001"
ORACLE_DIR = Path(__file__).resolve().parents[2] / "backend" / "judge" / "oracle"

TAG_VERDICTS = {
    "ma": "OK",
    "ok": "OK",
    "wa": "WA",
    "tl": "TLE",
    "ml": "MLE",
    "re": "RE",
    "pe": "PE",
}

LANGUAGES = {".cpp": "cpp", ".py": "python"}


def judge(problem: dict, checker: str, source: str, language: str) -> dict:
    payload = {
        "source": source,
        "language": language,
        "checker": checker,
        "time_limit_ms": problem.get("time_limit_ms", 1000),
        "memory_limit_mb": problem.get("memory_limit_mb", 256),
        "tests": [
            {
                "index": i,
                "input": base64.b64encode(test["input"].encode()).decode(),
                "answer": base64.b64encode(test["answer"].encode()).decode(),
                "points": test.get("points", 0),
                "group": test.get("group"),
            }
            for i, test in enumerate(problem["tests"], start=1)
        ],
    }
    request = urllib.request.Request(
        f"{JUDGE_URL}/judge",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        return json.load(response)


def collect(problem_dir: Path) -> list[tuple[str, str, str, str]]:
    """Return (label, expected verdict, language, source) per solution."""
    found = []
    for path in sorted((problem_dir / "solutions").iterdir()):
        language = LANGUAGES.get(path.suffix)
        if language is None:
            continue
        tag = path.name.split("_", 1)[0].lower()
        expected = TAG_VERDICTS.get(tag)
        if expected is None:
            print(f"  ! {path.name}: unknown tag '{tag}', skipped")
            continue
        found.append((path.name, expected, language, path.read_text()))
    return found


def main() -> int:
    problems = sorted(p for p in ORACLE_DIR.iterdir() if (p / "problem.json").exists())
    if not problems:
        print(f"no oracle problems under {ORACLE_DIR}")
        return 2

    mismatches = []
    for problem_dir in problems:
        problem = json.loads((problem_dir / "problem.json").read_text())
        checker = (problem_dir / "checker.cpp").read_text()
        print(f"\n{problem.get('name', problem_dir.name)}  ({problem_dir.name})")
        print(f"{'solution':<24} {'want':<5} {'got':<5} {'score':>6} {'time':>8} {'memory':>10}")
        print("-" * 72)

        for label, expected, language, source in collect(problem_dir):
            try:
                result = judge(problem, checker, source, language)
            except urllib.error.URLError as exc:
                print(f"cannot reach the judge at {JUDGE_URL}: {exc}")
                return 2
            got = result["verdict"]
            mark = " " if got == expected else "  <-- MISMATCH"
            print(
                f"{label:<24} {expected:<5} {got:<5} {result['score']:>6} "
                f"{result['max_time_ms']:>6}ms {result['max_memory_kb']:>8}kb{mark}"
            )
            if got != expected:
                detail = result["compile_log"].replace("\n", " ")[:120]
                mismatches.append((problem_dir.name, label, expected, got, detail))

    print()
    if mismatches:
        print(f"{len(mismatches)} mismatch(es):")
        for problem_name, label, expected, got, detail in mismatches:
            print(f"  {problem_name}/{label}: expected {expected}, got {got} {detail}")
        return 1
    print("every solution got the verdict its tag claims")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
