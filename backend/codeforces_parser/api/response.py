from aiohttp import ClientSession


async def get_response(client: ClientSession, url, params):
    async with client.post(str(url), data=params) as response:
        if response.status == 200:
            result = await response.json()

            return result['result']
        print(response.status)
        print(await response.text())
        if response.status == 400:
            result = await response.json()
            raise AttributeError(result['comment'])
        raise RuntimeError('Oops! Something went wrong. We are already working to fix it!')
