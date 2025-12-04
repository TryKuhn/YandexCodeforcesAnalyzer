from asyncio import create_task, gather

from aiohttp import ClientSession, TCPConnector
from codeforces_parser.api_cf.request_signer import gen_borders, gen_params
from codeforces_parser.api_cf.response import get_response
from yarl import URL

from settings import CODEFORCES_HOST


async def submission(
    client: ClientSession, oauth: tuple[str, str], contest_id: str, submission_id: str
) -> str:
    method_name = f"contest.{submission.__name__}"

    params = gen_params(
        oauth, method_name, contestId=contest_id, submissionID=submission_id
    )

    url = URL(CODEFORCES_HOST) / method_name

    return await get_response(client, url, params)


async def status(
    client: ClientSession,
    oauth: tuple[str, str],
    contest_id: str,
    from_pos: int = None,
    to_pos: int = None,
) -> dict:
    method_name = f"contest.{status.__name__}"

    from_pos, to_pos = gen_borders(from_pos, to_pos)
    params = gen_params(
        oauth,
        method_name,
        contestId=contest_id,
        From=from_pos,
        count=to_pos - from_pos + 1,
    )

    url = URL(CODEFORCES_HOST) / method_name

    return await get_response(client, url, params)


async def submissions(
    oauth: tuple[str, str], contest_id: str, from_pos: int = None, to_pos: int = None
):
    connector = TCPConnector(limit=400)
    async with ClientSession(connector=connector) as client:
        submission_list = await status(client, oauth, contest_id, from_pos, to_pos)

        tasks = [
            create_task(
                submission(client, oauth, contest_id, str(submission_info["id"]))
            )
            for submission_info in submission_list
        ]
        submission_sources = await gather(*tasks)

        for submission_info, submission_source in zip(
            submission_list, submission_sources
        ):
            submission_info["source"] = submission_source

        return submission_list
