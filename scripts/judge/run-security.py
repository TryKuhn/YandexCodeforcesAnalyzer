#!/usr/bin/env python3
"""Run the sandbox escape attempts and check the sandbox held (YCA-412).

Needs the judge service running:
    docker compose -f docker-compose.dev.yml up -d --build judge
    ./scripts/judge/run-security.py
"""
import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

JUDGE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001"
SUITE_DIR = Path(__file__).resolve().parents[2] / "backend" / "judge" / "security"
CHECKER = (
    Path(__file__).resolve().parents[2]
    / "backend" / "judge" / "oracle" / "aplusb" / "checker.cpp"
)


def judge(problem: dict, checker: str, source: str) -> dict:
    payload = {
        "source": source,
        "language": "cpp",
        "checker": checker,
        "time_limit_ms": problem["time_limit_ms"],
        "memory_limit_mb": problem["memory_limit_mb"],
        "tests": [
            {
                "index": i,
                "input": base64.b64encode(test["input"].encode()).decode(),
                "answer": base64.b64encode(test["answer"].encode()).decode(),
                "points": test.get("points", 0),
            }
            for i, test in enumerate(problem["tests"], start=1)
        ],
    }
    request = urllib.request.Request(
        f"{JUDGE_URL}/judge",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=300) as response:
        return json.load(response)


def main() -> int:
    suite = json.loads((SUITE_DIR / "suite.json").read_text())
    problem = suite["problem"]
    checker = CHECKER.read_text()

    print(f"sandbox escape attempts against {JUDGE_URL}\n")
    print(f"{'attack':<28} {'accepted':<12} {'got':<5} {'held':<5}  why")
    print("-" * 100)

    breaches = []
    for attack in suite["attacks"]:
        source = (SUITE_DIR / "attacks" / attack["file"]).read_text()
        try:
            result = judge(problem, checker, source)
        except urllib.error.URLError as exc:
            print(f"cannot reach the judge at {JUDGE_URL}: {exc}")
            return 2

        got = result["verdict"]
        held = got in attack["accept"]
        print(
            f"{attack['file']:<28} {'/'.join(attack['accept']):<12} {got:<5} "
            f"{'yes' if held else 'NO':<5}  {attack['why']}"
        )
        if not held:
            breaches.append((attack["file"], attack["accept"], got, attack["why"]))

    print()
    if breaches:
        print(f"{len(breaches)} sandbox breach(es):")
        for name, accept, got, why in breaches:
            print(f"  {name}: expected {'/'.join(accept)}, got {got} -- {why}")
        return 1
    print("the sandbox held against every attack")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
