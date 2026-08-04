"""Running a testlib checker; its exit code is the verdict, never a diff."""
from dataclasses import dataclass

from ..sandbox import RunLimits, RunStatus, SandboxSession
from .verdict import Verdict

# testlib exit codes
_OK = 0
_WA = 1
_PE = 2
_FAIL = 3
_DIRT = 4
_POINTS = 7
_UNEXPECTED_EOF = 8

_EXIT_TO_VERDICT = {
    _OK: Verdict.OK,
    _WA: Verdict.WRONG_ANSWER,
    _PE: Verdict.PRESENTATION_ERROR,
    # _dirt: correct answer followed by trailing garbage
    _DIRT: Verdict.PRESENTATION_ERROR,
    _UNEXPECTED_EOF: Verdict.PRESENTATION_ERROR,
    # _fail means the checker itself is broken, not the solution
    _FAIL: Verdict.INTERNAL_ERROR,
}

CHECKER_BINARY = "checker"
_COMMENT_FILE = "checker.err"
_COMMENT_LIMIT = 1024

# a checker compares, it should never need the solution's budget
_CHECKER_LIMITS = RunLimits(cpu_time_ms=10_000, memory_kb=512 * 1024, max_processes=4)


@dataclass(frozen=True)
class CheckOutcome:
    verdict: Verdict
    comment: str = ""
    # set by testlib's quitp(): fraction of the test's points, 0..1
    points_ratio: float | None = None


def _parse_points(comment: str) -> float | None:
    """testlib reports partial score as 'points 0.5' in its comment."""
    marker = "points "
    if marker not in comment:
        return None
    tail = comment.split(marker, 1)[1].split()
    if not tail:
        return None
    try:
        return max(0.0, min(1.0, float(tail[0])))
    except ValueError:
        return None


async def run_checker(
    session: SandboxSession,
    *,
    input_name: str,
    output_name: str,
    answer_name: str,
) -> CheckOutcome:
    """Compare output against answer using the compiled testlib checker."""
    result = await session.run(
        (f"./{CHECKER_BINARY}", input_name, output_name, answer_name),
        _CHECKER_LIMITS,
        stderr=_COMMENT_FILE,
    )
    comment = (
        await session.read_file(_COMMENT_FILE, max_bytes=_COMMENT_LIMIT)
    ).decode(errors="replace").strip()

    if result.status is RunStatus.TIME_LIMIT:
        return CheckOutcome(Verdict.INTERNAL_ERROR, "checker timed out")
    if result.status is RunStatus.INTERNAL_ERROR:
        return CheckOutcome(Verdict.INTERNAL_ERROR, comment or result.message)

    if result.exit_code == _POINTS:
        ratio = _parse_points(comment)
        # partial credit still counts as a pass on the test
        return CheckOutcome(Verdict.OK, comment, points_ratio=ratio if ratio is not None else 0.0)

    verdict = _EXIT_TO_VERDICT.get(result.exit_code)
    if verdict is None:
        # unknown code: the checker is misbehaving, do not punish the solution
        return CheckOutcome(
            Verdict.INTERNAL_ERROR, comment or f"checker exit code {result.exit_code}"
        )
    return CheckOutcome(verdict, comment)
