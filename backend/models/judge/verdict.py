"""Canonical verdict codes of our judge."""
import enum


class JudgeVerdict(str, enum.Enum):
    OK = "OK"
    WRONG_ANSWER = "WA"
    TIME_LIMIT = "TLE"
    MEMORY_LIMIT = "MLE"
    RUNTIME_ERROR = "RE"
    PRESENTATION_ERROR = "PE"
    COMPILE_ERROR = "CE"
    # the judge itself broke; never a contestant's fault
    INTERNAL_ERROR = "XX"
