from aiohttp import ClientSession
from codeforces_parser.api_cf.request_signer import gen_borders, gen_params
from codeforces_parser.api_cf.response import get_response
from yarl import URL

from settings import CODEFORCES_HOST


async def standings(
    oauth: tuple[str, str], contest_id: str, from_pos: int = None, to_pos: int = None
):
    method_name = f"contest.{standings.__name__}"

    from_pos, to_pos = gen_borders(from_pos, to_pos)
    params = gen_params(
        oauth,
        method_name,
        contestId=contest_id,
        From=from_pos,
        count=to_pos - from_pos + 1,
    )

    url = URL(CODEFORCES_HOST) / method_name

    async with ClientSession() as client:
        return await get_response(client, url, params)
