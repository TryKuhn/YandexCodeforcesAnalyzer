from typing import Optional

from api_ya.results_parser import parse_results
from api_ya.submission_parser import parse_submissions

from yandex_parser.api_ya.login import link, token
from yandex_parser.api_ya.problems import problems
from yandex_parser.api_ya.standings import contest_info, standings
from yandex_parser.api_ya.submissions import submissions


class ApiYandex:
    register_link = link
    register_token = token

    @staticmethod
    async def get_standings(
            oauth: str,
            contest_id: str,
            from_pos: Optional[int] = None,
            to_pos: Optional[int] = None,
    ) -> tuple[str, dict]:
        names = await problems(oauth, contest_id)
        results = await standings(oauth, contest_id, from_pos, to_pos)
        contest = await contest_info(oauth, contest_id)

        return parse_results(results, names, contest)

    @staticmethod
    async def get_submissions(
            oauth: str,
            contest_id: str,
            from_pos: Optional[int] = None,
            to_pos: Optional[int] = None,
    ) -> dict:
        names = await problems(oauth, contest_id)
        submissions_list = await submissions(oauth, contest_id, from_pos, to_pos)

        return parse_submissions(submissions_list, names)
