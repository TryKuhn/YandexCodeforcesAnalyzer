from logs import log_middleware
from yandex_parser.api.login import link, token
from yandex_parser.api.problems import problems
from yandex_parser.api.standings import standings, contest_info
from yandex_parser.parse_results.results_parser import parse_results
from yandex_parser.api.submissions import submissions
from yandex_parser.parse_submissions.submission_parser import parse_submissions


class ApiYandex:
    register_link = link
    register_token = token

    @staticmethod
    @log_middleware
    async def get_standings(oauth: str, contest_id: str, from_pos: int = None, to_pos: int = None) -> tuple[str, dict]:
        names = await problems(oauth, contest_id)
        results = await standings(oauth, contest_id, from_pos, to_pos)
        contest = await contest_info(oauth, contest_id)

        return parse_results(results, names, contest)

    @staticmethod
    @log_middleware
    async def get_submissions(oauth: str, contest_id: str, from_pos: int = None, to_pos: int = None) -> dict:
        names = await problems(oauth, contest_id)
        submissions_list = await submissions(oauth, contest_id, from_pos, to_pos)

        return parse_submissions(submissions_list, names)
