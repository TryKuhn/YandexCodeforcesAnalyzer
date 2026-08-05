"""Stress testing: find a test where a candidate disagrees with the jury solution."""
from .result import Counterexample, StressResult
from .runner import StressTester

__all__ = ["Counterexample", "StressResult", "StressTester"]
