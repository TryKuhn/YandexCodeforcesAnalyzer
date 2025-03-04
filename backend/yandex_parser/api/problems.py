import requests

from yandex_parser.appCredentials import yandex_host


def problems(token: str, contest_id: str):
    headers = {
        'Authorization': f'OAuth {token}'
    }

    result = requests.get(yandex_host + '/contests/' + contest_id + '/problems', headers=headers)

    if result.status_code == 200:
        result = result.json()['problems']
        names = list()

        for problem in result:
            names.append([problem['name'], problem['alias']])

        names.sort(key=lambda x: x[1])

        return names
    elif result.status_code == 403:
        raise PermissionError('You do not have permission to this contest!')
    elif result.status_code == 404:
        raise PermissionError('Contest is not found!')
    else:
        # save_log(OAuthToken.json()['error_description'], 'while getting problems',
        # token, contest_id)
        raise RuntimeError('Oops! Something went wrong. We are already working to fix it!')
