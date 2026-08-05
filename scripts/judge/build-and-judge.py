#!/usr/bin/env python3
"""Build A+B from jury sources, then judge solutions against the built package (YCA-404).

Proves the loop closes without Polygon: our generator makes the tests, our
validator accepts them, our reference solution supplies the answers, and the
resulting package is good enough to judge with.

    ./scripts/judge/build-and-judge.py
"""
import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

JUDGE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001"
PROBLEM = Path(__file__).resolve().parents[2] / "backend" / "judge" / "oracle" / "aplusb"

BAD_TEST = "999999999999 1\n"


def post(path: str, payload: dict) -> dict:
    request = urllib.request.Request(
        f"{JUDGE_URL}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.load(response)


def read(name: str) -> str:
    return (PROBLEM / name).read_text()


def build(tests: list[dict], validator: str | None) -> dict:
    return post(
        "/authoring/build",
        {
            "name": "aplusb",
            "main_solution": read("solutions/ma_correct.cpp"),
            "checker": read("checker.cpp"),
            "generator": read("generator.cpp"),
            "validator": validator,
            "time_limit_ms": 1000,
            "memory_limit_mb": 64,
            "tests": tests,
        },
    )


def main() -> int:
    print(f"building aplusb from jury sources against {JUDGE_URL}\n")

    planned = [
        {"input": base64.b64encode(b"2 3\n").decode(), "points": 20},
        {"args": "10 1", "points": 20},
        {"args": "1000000000 2", "points": 30},
        {"args": "1000000000 3", "points": 30},
    ]
    try:
        package = build(planned, read("validator.cpp"))
    except urllib.error.URLError as exc:
        print(f"cannot reach the judge at {JUDGE_URL}: {exc}")
        return 2

    if not package["ok"]:
        print(f"build failed at {package['failed_stage']}: {package['error']}")
        print(package["log"])
        return 1

    print(f"{'test':<6} {'origin':<26} {'points':>7}  input -> answer")
    print("-" * 78)
    for test in package["tests"]:
        raw_input = base64.b64decode(test["input"]).decode().strip()
        answer = base64.b64decode(test["answer"]).decode().strip()
        print(f"{test['index']:<6} {test['origin']:<26} {test['points']:>7}  {raw_input} -> {answer}")

    # the reference solution must agree with its own answers
    a, b = map(int, base64.b64decode(package["tests"][0]["input"]).split())
    if base64.b64decode(package["tests"][0]["answer"]).strip() != str(a + b).encode():
        print("\nthe jury solution disagrees with the answer it produced")
        return 1

    print(f"\nbuilt {len(package['tests'])} tests, {package['total_points']} points total")

    print("\nrejecting an invalid test:")
    broken = build([{"input": base64.b64encode(BAD_TEST.encode()).decode()}], read("validator.cpp"))
    if broken["ok"]:
        print("  the validator accepted an out-of-range test")
        return 1
    print(f"  blocked at {broken['failed_stage']}: {broken['error']}")

    print("\njudging solutions against the freshly built package:")
    expectations = {"solutions/ma_correct.cpp": "OK", "solutions/wa_subtracts.cpp": "WA"}
    for path, expected in expectations.items():
        verdict = post(
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
        got = verdict["verdict"]
        print(f"  {path:<28} want {expected:<4} got {got:<4} score {verdict['score']}")
        if got != expected:
            print("  verdict does not match the package")
            return 1

    print("\nthe authoring loop closes without Polygon")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
