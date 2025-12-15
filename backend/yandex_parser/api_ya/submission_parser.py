from collections import defaultdict
from typing import Any, Dict


def parse_submissions(submissions: list, names: list) -> dict:
    names_compare: Dict[str, str] = {}

    for name, alias in names:
        names_compare[alias] = name

    submissions_result: Dict[str, Any] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )

    for submission in submissions:
        task_alias = submission["problemAlias"]
        task_name = names_compare[task_alias]

        author = submission["author"]

        source = submission["source"]

        verdict = submission["verdict"]

        submissions_result[task_name][author][verdict].append(source)

    return submissions_result
