from aiohttp import ClientSession
from yarl import URL

from codeforces_parser.api.request_signer import gen_params, gen_borders
from codeforces_parser.api.response import get_response
from settings import CODEFORCES_HOST


async def standings(oauth: tuple[str, str], contest_id: str, from_pos: int = None, to_pos: int = None):
    method_name = f'contest.{standings.__name__}'

    from_pos, to_pos = gen_borders(from_pos, to_pos)
    params = gen_params(oauth, method_name, contestId=contest_id, From=from_pos, count=(to_pos - from_pos + 1))

    url = URL(CODEFORCES_HOST) / method_name

    async with ClientSession() as client:
        return await get_response(client, url, params)
