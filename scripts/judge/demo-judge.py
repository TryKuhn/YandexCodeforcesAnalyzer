#!/usr/bin/env python3
"""Judge four A+B solutions and print the verdicts (YCA-406 demo).

Needs the judge service running:
    docker compose -f docker-compose.dev.yml up -d --build judge
    ./scripts/judge/demo-judge.py
"""
import base64
import json
import sys
import urllib.error
import urllib.request

JUDGE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8001"

CHECKER = r"""
#include "testlib.h"
int main(int argc, char* argv[]) {
    registerTestlibCmd(argc, argv);
    long long jury = ans.readLong();
    long long participant = ouf.readLong();
    if (jury != participant)
        quitf(_wa, "expected %lld, found %lld", jury, participant);
    quitf(_ok, "answer is %lld", jury);
}
"""

SOLUTIONS = {
    "correct": r"""
#include <iostream>
int main() { long long a, b; std::cin >> a >> b; std::cout << a + b << "\n"; }
""",
    "wrong answer": r"""
#include <iostream>
int main() { long long a, b; std::cin >> a >> b; std::cout << a - b << "\n"; }
""",
    "time limit": r"""
#include <iostream>
int main() { long long a, b; std::cin >> a >> b; while (true) {} }
""",
    "memory limit": r"""
#include <iostream>
#include <vector>
int main() {
    long long a, b; std::cin >> a >> b;
    std::vector<std::vector<long long>> hog;
    while (true) hog.emplace_back(1 << 20, 7);
}
""",
    "runtime error": r"""
#include <iostream>
int main() { long long a, b; std::cin >> a >> b; int* p = nullptr; std::cout << *p; }
""",
}

TESTS = [(b"2 3\n", b"5\n"), (b"1000000 2000000\n", b"3000000\n")]


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def judge(name: str, source: str) -> dict:
    payload = {
        "source": source,
        "language": "cpp",
        "checker": CHECKER,
        "time_limit_ms": 1000,
        "memory_limit_mb": 64,
        "tests": [
            {"index": i, "input": b64(inp), "answer": b64(ans), "points": 50}
            for i, (inp, ans) in enumerate(TESTS, start=1)
        ],
    }
    request = urllib.request.Request(
        f"{JUDGE_URL}/judge",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.load(response)


def main() -> int:
    print(f"judging against {JUDGE_URL}\n")
    print(f"{'solution':<16} {'verdict':<8} {'score':>6} {'time':>8} {'memory':>10}  comment")
    print("-" * 78)
    expected = {
        "correct": "OK",
        "wrong answer": "WA",
        "time limit": "TLE",
        "memory limit": "MLE",
        "runtime error": "RE",
    }
    failures = 0
    for name, source in SOLUTIONS.items():
        try:
            result = judge(name, source)
        except urllib.error.URLError as exc:
            print(f"cannot reach the judge: {exc}")
            return 2
        comment = next((t["comment"] for t in result["tests"] if t["comment"]), "")
        print(
            f"{name:<16} {result['verdict']:<8} {result['score']:>6} "
            f"{result['max_time_ms']:>6}ms {result['max_memory_kb']:>8}kb  {comment[:30]}"
        )
        if result["verdict"] != expected[name]:
            failures += 1
    print()
    if failures:
        print(f"{failures} solution(s) did not get the expected verdict")
        return 1
    print("every solution got the verdict it deserves")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
