from logs import log_middleware

from codeforces_parser.api.standings import standings
from codeforces_parser.api.submissions import submissions
from codeforces_parser.parse_submissions.submission_parser import parse_submissions
from codeforces_parser.parse_results.results_parser import parse_results


class ApiCodeforces:
    @staticmethod
    @log_middleware
    async def get_standings(oauth: tuple[str, str], contest_id: str, from_pos: int = None, to_pos: int = None):
        full_standings = await standings(oauth, contest_id, from_pos, to_pos)

        names = full_standings['problems']
        results = full_standings['rows']
        contest = full_standings['contest']

        return parse_results(results, names, contest)

    @staticmethod
    @log_middleware
    async def get_submissions(oauth: tuple[str, str], contest_id: str, from_pos: int = None, to_pos: int = None):
        submissions_list = await submissions(oauth, contest_id, from_pos, to_pos)

        return parse_submissions(submissions_list)
