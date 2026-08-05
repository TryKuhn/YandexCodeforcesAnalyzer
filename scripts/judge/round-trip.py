#!/usr/bin/env python3
"""Export a built problem, import it back, and check nothing changed (YCA-411).

Runs the loop through every registered format, Polygon included: build locally,
export, materialize, then judge with the restored package. Verdicts must match.

    ./scripts/judge/round-trip.py
"""
import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

JUDGE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001"
PROBLEM = Path(__file__).resolve().parents[2] / "backend" / "judge" / "oracle" / "aplusb"

EXPECTED = {"solutions/ma_correct.cpp": "OK", "solutions/wa_subtracts.cpp": "WA"}


def post(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        f"{JUDGE_URL}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.load(response)


def get(path: str) -> dict:
    with urllib.request.urlopen(f"{JUDGE_URL}{path}", timeout=60) as response:
        return json.load(response)


def read(name: str) -> str:
    return (PROBLEM / name).read_text()


def judge_all(package: dict) -> dict[str, str]:
    verdicts = {}
    for path in EXPECTED:
        result = post(
            "/judge",
            {
                "source": read(path),
                "language": "cpp",
                "checker": package["checker"],
                "time_limit_ms": package["time_limit_ms"],
                "memory_limit_mb": package["memory_limit_mb"],
                "tests": [
                    {
                        "index": t["index"],
                        "input": t["input"],
                        "answer": t["answer"],
                        "points": t["points"],
                    }
                    for t in package["tests"]
                ],
            },
        )
        verdicts[path] = result["verdict"]
    return verdicts


def main() -> int:
    print(f"round trip against {JUDGE_URL}\n")

    try:
        formats = get("/packaging/formats")["formats"]
    except urllib.error.URLError as exc:
        print(f"cannot reach the judge at {JUDGE_URL}: {exc}")
        return 2

    built = post(
        "/authoring/build",
        {
            "name": "aplusb",
            "main_solution": read("solutions/ma_correct.cpp"),
            "checker": read("checker.cpp"),
            "generator": read("generator.cpp"),
            "validator": read("validator.cpp"),
            "time_limit_ms": 1000,
            "memory_limit_mb": 64,
            "tests": [
                {"input": base64.b64encode(b"2 3\n").decode(), "points": 40},
                {"args": "1000 7", "points": 60},
            ],
        },
    )
    if not built["ok"]:
        print(f"build failed at {built['failed_stage']}: {built['error']}")
        return 1

    package = {
        "name": "aplusb",
        "checker": built["checker"],
        "time_limit_ms": built["time_limit_ms"],
        "memory_limit_mb": built["memory_limit_mb"],
        "tests": built["tests"],
    }
    baseline = judge_all(package)
    print(f"built locally: {len(package['tests'])} tests, verdicts {baseline}\n")

    failures = 0
    for fmt in formats:
        exported = post(
            "/packaging/export",
            {
                "name": package["name"],
                "checker": package["checker"],
                "time_limit_ms": package["time_limit_ms"],
                "memory_limit_mb": package["memory_limit_mb"],
                "tests": [
                    {
                        "index": t["index"],
                        "input": t["input"],
                        "answer": t["answer"],
                        "group": t.get("group"),
                        "points": t["points"],
                    }
                    for t in package["tests"]
                ],
                "format": fmt,
            },
        )
        size = len(base64.b64decode(exported["archive"]))
        restored = post(
            "/packaging/import", {"archive": exported["archive"], "format": fmt}
        )

        same_tests = [
            (t["input"], t["answer"]) for t in restored["tests"]
        ] == [(t["input"], t["answer"]) for t in package["tests"]]
        verdicts = judge_all(restored)

        ok = same_tests and verdicts == baseline
        print(f"{fmt:<10} archive {size:>6}b  tests {'same' if same_tests else 'CHANGED'}"
              f"  verdicts {verdicts}  {'ok' if ok else 'MISMATCH'}")
        if not ok:
            failures += 1

    print()
    if failures:
        print(f"{failures} format(s) did not survive the round trip")
        return 1
    print("every format survives export and import unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
