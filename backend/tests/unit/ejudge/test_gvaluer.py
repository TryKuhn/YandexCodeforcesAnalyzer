"""Our valuer.cfg run through ejudge's real gvaluer (compiled from the vendored source).

Checks that the Polygon semantics survive: a group gives its points only when
all its tests pass, a failed test skips the rest of the group, and a group
whose dependency failed is not judged at all.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from api.user.ejudge.convert import GVALUER_SOURCE, build_plan
from api.user.ejudge.package import parse_package
from api.user.ejudge.servecfg import ServeCfg
from tests.unit.ejudge.helpers import SERVE_CFG, package_zip
from tests.unit.ejudge.test_convert import GROUPED_TESTS, GROUPS

OK, WA = 0, 5

pytestmark = pytest.mark.skipif(shutil.which("g++") is None, reason="needs g++")


@pytest.fixture(scope="module")
def gvaluer(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("gvaluer") / "gvaluer"
    subprocess.run(["g++", "-O2", "-std=c++17", "-o", str(out), str(GVALUER_SOURCE)], check=True)
    return out


def judge(gvaluer: Path, problem_dir: Path, verdicts: dict[int, int], tests: int) -> tuple[int, list[int]]:
    """Play ejudge's side of the interactive valuer protocol; (score, judged tests)."""
    env = {**os.environ, "EJUDGE": "1", "EJUDGE_INTERACTIVE": "1"}
    proc = subprocess.Popen(
        [str(gvaluer), str(problem_dir / "c1"), str(problem_dir / "c2"), str(problem_dir)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, env=env,
    )
    assert proc.stdin and proc.stdout
    proc.stdin.write("-1\n")
    judged, current = [], 1
    while current <= tests:
        judged.append(current)
        status = verdicts.get(current, OK)
        proc.stdin.write(f"{status} 0 10\n")
        proc.stdin.flush()
        reply = int(proc.stdout.readline())
        current = current + 1 if reply == -1 else -reply
    proc.stdin.close()
    score = int(proc.stdout.read().split()[0])
    proc.wait(timeout=10)
    return score, judged


@pytest.fixture
def problem_dir(tmp_path) -> Path:
    plan = build_plan(parse_package(package_zip(GROUPED_TESTS, GROUPS)), ServeCfg(SERVE_CFG), polygon_id=1)
    (tmp_path / "valuer.cfg").write_text(plan.valuer_cfg or "")
    return tmp_path


@pytest.mark.parametrize("verdicts, score, judged", [
    ({}, 100, [1, 2, 3, 4, 5, 6, 7, 8]),
    ({8: WA}, 30, [1, 2, 3, 4, 5, 6, 7, 8]),
    ({4: WA}, 0, [1, 2, 3, 4]),             # group 1 fails at test 4, group 2 needs group 1
    ({7: WA}, 30, [1, 2, 3, 4, 5, 6, 7]),
    ({1: WA}, 0, [1]),                       # samples failed: nothing else is judged
])
def test_polygon_semantics_in_gvaluer(gvaluer, problem_dir, verdicts, score, judged):
    assert judge(gvaluer, problem_dir, verdicts, 8) == (score, judged)
