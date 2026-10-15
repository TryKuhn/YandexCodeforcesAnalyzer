"""Allowed values of enum-like Polygon API parameters.

Source: https://codeforces.github.io/polygon-misc/API. Values are validated
locally (``client.choice``) so a typo like ``complete-group`` fails fast with a
clear error instead of being rejected (or ignored) by Polygon.
"""

FILE_TYPES = ("resource", "source", "aux")
PACKAGE_TYPES = ("standard", "linux", "windows")

SOLUTION_TAGS = ("MA", "OK", "RJ", "TL", "TO", "TM", "WA", "PE", "ML", "NR", "RE")
# editSolutionExtraTags does not accept MA.
EXTRA_SOLUTION_TAGS = tuple(t for t in SOLUTION_TAGS if t != "MA")

ACCESS_TYPES = ("READ", "WRITE", "NONE")

POINTS_POLICIES = ("COMPLETE_GROUP", "EACH_TEST")
FEEDBACK_POLICIES = ("NONE", "POINTS", "ICPC", "COMPLETE")

VALIDATOR_TEST_VERDICTS = ("VALID", "INVALID")
CHECKER_TEST_VERDICTS = ("OK", "WRONG_ANSWER", "PRESENTATION_ERROR", "CRASHED")

ISSUE_TYPES = ("DISCUSSION", "ENHANCEMENT", "BUG")
ISSUE_UPDATE_STATUSES = ("CLOSED", "REOPENED")

MATERIAL_PUBLISH_STRATEGIES = ("NONE", "WITH_TUTORIAL", "WITH_STATEMENT")
MATERIAL_ITEM_TYPES = (
    "TEST_INPUTS",
    "TEST_ANSWERS",
    "RESOURCE_FILES",
    "SOURCE_FILES",
    "AUX_FILES",
    "SOLUTIONS",
)

# problem.updateInfo limits.
TIME_LIMIT_RANGE = (250, 15000)  # ms, a multiple of 50
MEMORY_LIMIT_RANGE = (4, 1024)  # MB
