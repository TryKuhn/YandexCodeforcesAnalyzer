from typing import Optional

from api_cf.results_parser import parse_results
from api_cf.submission_parser import parse_submissions
from codeforces_parser.api_cf.standings import standings
from codeforces_parser.api_cf.submissions import submissions
from logs.logs import log_middleware


class ApiCodeforces:
    @staticmethod
    @log_middleware
    async def get_standings(
        oauth: tuple[str, str],
        contest_id: str,
        from_pos: Optional[int] = None,
        to_pos: Optional[int] = None,
    ):
        full_standings = await standings(oauth, contest_id, from_pos, to_pos)

        names = full_standings["problems"]
        results = full_standings["rows"]
        contest = full_standings["contest"]

        return parse_results(results, names, contest)

    @staticmethod
    @log_middleware
    async def get_submissions(
        oauth: tuple[str, str],
        contest_id: str,
        from_pos: Optional[int] = None,
        to_pos: Optional[int] = None,
    ):
        submissions_list = await submissions(oauth, contest_id, from_pos, to_pos)

        return parse_submissions(submissions_list)
