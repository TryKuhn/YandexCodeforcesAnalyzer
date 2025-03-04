from collections import defaultdict


def parse_submissions(submissions, names):
    names_compare = dict()

    for name, alias in names:
        names_compare[alias] = name

    submissions_result = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for submission in submissions:
        task_alias = submission['problemAlias']
        task_name = names_compare[task_alias]

        author = submission['author']

        source = submission['source']

        verdict = submission['verdict']

        submissions_result[task_name][author][verdict].append(source)

    return submissions_result
