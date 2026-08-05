"""Verdicts and how a sandbox outcome becomes one."""
import enum

from ..sandbox import RunStatus


class Verdict(str, enum.Enum):
    OK = "OK"
    WRONG_ANSWER = "WA"
    TIME_LIMIT = "TLE"
    MEMORY_LIMIT = "MLE"
    RUNTIME_ERROR = "RE"
    PRESENTATION_ERROR = "PE"
    COMPILE_ERROR = "CE"
    # the judge itself broke; never blamed on the contestant
    INTERNAL_ERROR = "XX"


_FROM_RUN = {
    RunStatus.TIME_LIMIT: Verdict.TIME_LIMIT,
    RunStatus.MEMORY_LIMIT: Verdict.MEMORY_LIMIT,
    RunStatus.RUNTIME_ERROR: Verdict.RUNTIME_ERROR,
    # writing gigabytes is the solution's fault, closest honest verdict is RE
    RunStatus.OUTPUT_LIMIT: Verdict.RUNTIME_ERROR,
    RunStatus.INTERNAL_ERROR: Verdict.INTERNAL_ERROR,
}


def from_run_status(status: RunStatus) -> Verdict | None:
    """Verdict implied by how the process ended; None means the run was clean."""
    return _FROM_RUN.get(status)
