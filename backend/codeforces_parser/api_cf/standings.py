from typing import Optional

from aiohttp import ClientSession
from yarl import URL

from backend.codeforces_parser.api_cf.request_signer import (gen_borders,
                                                             gen_params)
from backend.codeforces_parser.api_cf.response import get_response
from settings import CODEFORCES_HOST


async def standings(
    oauth: tuple[str, str], contest_id: str, from_pos: Optional[int] = None, to_pos: Optional[int] = None
):
    method_name = f"contest.{standings.__name__}"

    from_pos_int: int
    to_pos_int: int
    from_pos_int, to_pos_int = gen_borders(from_pos, to_pos)
    params = gen_params(
        oauth,
        method_name,
        contestId=contest_id,
        From=from_pos_int,
        count=to_pos_int - from_pos_int + 1,
    )

    url = URL(CODEFORCES_HOST) / method_name

    async with ClientSession() as client:
        return await get_response(client, url, params)
