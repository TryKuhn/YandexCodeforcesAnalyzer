#!/usr/bin/env python3
"""Check the counterexample hunt works both ways (YCA-410).

A subtly broken candidate must be caught; a correct one must survive the whole
budget. The broken one here overflows only on large inputs, so finding it takes
an actual search rather than the first random test.

    ./scripts/judge/run-stress.py
"""
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

JUDGE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001"
PROBLEM = Path(__file__).resolve().parents[2] / "backend" / "judge" / "oracle" / "aplusb"

ROUNDS = 40

# int overflows past 2^31; correct only while the numbers stay small
OVERFLOWING = r"""
#include <iostream>
int main() {
    long long a, b;
    std::cin >> a >> b;
    int narrow = static_cast<int>(a) + static_cast<int>(b);
    std::cout << narrow << "\n";
}
"""


def post(payload: dict) -> dict:
    request = urllib.request.Request(
        f"{JUDGE_URL}/stress",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=600) as response:
        return json.load(response)


def read(name: str) -> str:
    return (PROBLEM / name).read_text()


def hunt(candidate: str, gen_args: str) -> dict:
    return post(
        {
            "candidate": candidate,
            "reference": read("solutions/ma_correct.cpp"),
            "generator": read("generator.cpp"),
            "checker": read("checker.cpp"),
            "gen_args": gen_args,
            "iterations": ROUNDS,
            "time_limit_ms": 1000,
            "memory_limit_mb": 64,
        }
    )


def main() -> int:
    print(f"stress testing against {JUDGE_URL}\n")

    try:
        broken = hunt(OVERFLOWING, "2000000000 {seed}")
    except urllib.error.URLError as exc:
        print(f"cannot reach the judge at {JUDGE_URL}: {exc}")
        return 2

    if broken["error"]:
        print(f"the hunt could not run: {broken['failed_stage']}: {broken['error']}")
        return 1

    print(f"broken candidate (int overflow): found={broken['found']} "
          f"after {broken['iterations']} round(s)")
    if not broken["found"]:
        print("  no counterexample found, but this candidate is definitely wrong")
        return 1

    example = broken["counterexample"]
    print(f"  seed {example['seed']}, {example['reason']}")
    print(f"  input    {example['input'].strip()}")
    print(f"  expected {example['expected'].strip()}")
    print(f"  got      {example['actual'].strip()}")

    print()
    # the same generator, but small numbers: the candidate is correct there
    survivor = hunt(OVERFLOWING, "1000 {seed}")
    print(f"same candidate on small inputs: found={survivor['found']} "
          f"after {survivor['iterations']} round(s)")
    if survivor["found"]:
        print("  a counterexample appeared where the candidate is actually correct")
        return 1

    correct = hunt(read("solutions/ma_correct.cpp"), "2000000000 {seed}")
    print(f"correct candidate: found={correct['found']} "
          f"after {correct['iterations']} round(s)")
    if correct["found"]:
        example = correct["counterexample"]
        print(f"  false alarm on {example['input'].strip()}: {example['reason']}")
        return 1

    print("\nthe hunt catches broken solutions and leaves correct ones alone")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
