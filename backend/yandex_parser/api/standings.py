import requests

from yandex_parser.appCredentials import yandex_host

DEFAULT_PAGE_SIZE = 100


def standings(token: str, contest_id: str, from_pos: int = None, to_pos: int = None):
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

    result = requests.get(yandex_host + '/contests/' + contest_id + '/standings', params=params, headers=headers)

    if result.status_code == 200:
        result = result.json()

        standings_slice = result['rows']

        if from_pos is not None:
            from_pos -= 1
            standings_slice = standings_slice[from_pos:to_pos]

        result['rows'] = standings_slice
        return result
    elif result.status_code == 400:
        raise PermissionError('Standings are not generated!')
    elif result.status_code == 403:
        raise PermissionError('You do not have permission to this contest!')
    elif result.status_code == 404:
        raise PermissionError('Contest is not found!')
    else:
        # save_log(OAuthToken.json()['error_description'], 'while getting standings',
        # token, contest_id, from_pos, to_pos)
        raise RuntimeError('Oops! Something went wrong. We are already working to fix it!')
