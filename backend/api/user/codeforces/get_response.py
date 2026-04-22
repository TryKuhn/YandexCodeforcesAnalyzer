import json

from aiohttp import ClientSession


async def get_response(client: ClientSession, url, params):
    async with client.post(url, data=params) as response:
        response_text = await response.text()

        try:
            result = json.loads(response_text)
        except json.JSONDecodeError:
            if response.status != 200:
                raise RuntimeError(f'HTTP {response.status}: {response_text[:200]}')
            else:
                return {'message': response_text}

        if result['status'] == 'OK':
            try:
                return result['result']
            except KeyError:
                return {'message': response_text}

        else:
            raise RuntimeError(result['comment'])