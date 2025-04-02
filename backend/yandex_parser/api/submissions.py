from asyncio import gather, create_task
from aiohttp import ClientSession, TCPConnector
from yarl import URL

from settings import YANDEX_HOST, DEFAULT_PAGE_SIZE


async def submission(client: ClientSession, token: str, contest_id: str, submission_id: str) -> str:
    headers = {
        'Authorization': f'OAuth {token}'
    }

    url = URL(YANDEX_HOST) / 'contests' / contest_id / 'submissions' / submission_id / 'source'

    async with client.get(str(url), headers=headers) as response:
        if response.status == 200:
            return await response.text()
        elif response.status == 403:
            raise PermissionError('You do not have permission to this contest!')
        elif response.status == 404:
            raise PermissionError('Contest is not found!')
        else:
            raise RuntimeError('Oops! Something went wrong. We are already working to fix it!')


async def submissions_info(client: ClientSession, token: str, contest_id: str, from_pos: int = None,
                           to_pos: int = None) -> dict:
    headers = {
        'Authorization': f'OAuth {token}'
    }

    params = {
        'page': 1
    }

    if to_pos is not None:
        params['pageSize'] = to_pos
    elif from_pos is not None:
        to_pos = from_pos + DEFAULT_PAGE_SIZE
        params['pageSize'] = to_pos

    url = URL(YANDEX_HOST) / 'contests' / contest_id / 'submissions'
    async with client.get(str(url), headers=headers, params=params) as response:
        if response.status == 200:
            data = await response.json()
            submission_list = data['submissions']

            if from_pos is not None:
                submission_list = submission_list[from_pos - 1:to_pos]

            return submission_list
        if response.status == 403:
            raise PermissionError('You do not have permission to this contest!')
        if response.status == 404:
            raise PermissionError('Contest is not found!')
        raise RuntimeError('Oops! Something went wrong. We are already working to fix it!')


async def submissions(token: str, contest_id: str, from_pos: int = None, to_pos: int = None):
    connector = TCPConnector(limit=400)
    async with ClientSession(connector=connector) as client:
        submission_list = await submissions_info(client, token, contest_id, from_pos, to_pos)

        tasks = [create_task(submission(client, token, contest_id, str(submission_info['id']))) for submission_info in
                 submission_list]
        submission_sources = await gather(*tasks)

        for (submission_info, submission_source) in zip(submission_list, submission_sources):
            submission_info['source'] = submission_source

        return submission_list
