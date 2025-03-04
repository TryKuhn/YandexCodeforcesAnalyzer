from yandex_parser.api.login import link, token
from yandex_parser.api.problems import problems
from yandex_parser.api.standings import standings
from yandex_parser.parse_results.resultsParser import parse_results
from yandex_parser.api.submissions import submissions
from yandex_parser.parse_submissions.submissionParser import parse_submissions


class ApiYandex:

    get_link = link
    get_token = token

    @staticmethod
    def get_standings(oauth: str, contest_id: str, from_pos: int = None, to_pos: int = None):
        names = problems(oauth, contest_id)
        results = standings(oauth, contest_id, from_pos, to_pos)

        return parse_results(results, names)

    @staticmethod
    def get_submissions(oauth: str, contest_id: str, from_pos: int = None, to_pos: int = None):
        names = problems(oauth, contest_id)
        submissions_list = submissions(oauth, contest_id, from_pos, to_pos)

        return parse_submissions(submissions_list, names)
