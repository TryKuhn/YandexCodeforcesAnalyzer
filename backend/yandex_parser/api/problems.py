from aiohttp import ClientSession
from yarl import URL

from settings import YANDEX_HOST


async def problems(token: str, contest_id: str) -> list:
    headers = {
        'Authorization': f'OAuth {token}'
    }

    url = URL(YANDEX_HOST) / 'contests' / contest_id / 'problems'

    async with ClientSession() as client:
        async with client.get(str(url), headers=headers) as response:
            if response.status == 200:
                result = await response.json()
                result = result['problems']

                names = []
                for problem in result:
                    names.append([problem['name'], problem['alias']])
                names.sort(key=lambda x: x[1])

                return names
            if response.status == 403:
                raise PermissionError('You do not have permission to this contest!')
            if response.status == 404:
                raise PermissionError('Contest is not found!')
            raise RuntimeError('Oops! Something went wrong. We are already working to fix it!')
