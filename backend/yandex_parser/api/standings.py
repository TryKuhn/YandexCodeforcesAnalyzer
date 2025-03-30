from yarl import URL
from aiohttp import ClientSession

from settings import YANDEX_HOST, DEFAULT_PAGE_SIZE


async def standings(token: str, contest_id: str, from_pos: int = None, to_pos: int = None):
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

    url = URL(YANDEX_HOST) / 'contests' / contest_id / 'standings'

    async with ClientSession() as client:
        async with client.get(str(url), params=params, headers=headers) as response:
            if response.status == 200:
                result = await response.json()

                standings_slice = result['rows']

                if from_pos is not None:
                    from_pos -= 1
                    standings_slice = standings_slice[from_pos:to_pos]

                result['rows'] = standings_slice
                return result
            elif response.status == 400:
                raise PermissionError('Standings are not generated!')
            elif response.status == 403:
                raise PermissionError('You do not have permission to this contest!')
            elif response.status == 404:
                raise PermissionError('Contest is not found!')
            else:
                raise RuntimeError('Oops! Something went wrong. We are already working to fix it!')
