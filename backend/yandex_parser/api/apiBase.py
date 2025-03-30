from logs.logs import log_middleware
from yandex_parser.api.login import link, token
from yandex_parser.api.problems import problems
from yandex_parser.api.standings import standings
from yandex_parser.parse_results.resultsParser import parse_results
from yandex_parser.api.submissions import submissions
from yandex_parser.parse_submissions.submissionParser import parse_submissions


class ApiYandex:
    register_link = link
    register_token = token

    @staticmethod
    @log_middleware
    async def login(login: str, password: str):
        pass

    @staticmethod
    @log_middleware
    async def get_standings(oauth: str, contest_id: str, from_pos: int = None, to_pos: int = None):
        names = await problems(oauth, contest_id)
        results = await standings(oauth, contest_id, from_pos, to_pos)

        return parse_results(results, names)

    @staticmethod
    @log_middleware
    async def get_submissions(oauth: str, contest_id: str, from_pos: int = None, to_pos: int = None):
        names = await problems(oauth, contest_id)
        submissions_list = await submissions(oauth, contest_id, from_pos, to_pos)

        return parse_submissions(submissions_list, names)
