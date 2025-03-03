import requests

from yandex_parser.appCredentials import yandex_host

DEFAULT_PAGE_SIZE = 100


def submission(token: str, contest_id: str, submission_id: str):
    headers = {
        'Authorization': f'OAuth {token}'
    }

    result = requests.get(yandex_host + '/contests/' + contest_id + '/submissions/' + submission_id + '/source',
                          headers=headers)

    if result.status_code == 200:
        return result.text
    elif result.status_code == 403:
        raise PermissionError('You do not have permission to this contest!')
    elif result.status_code == 404:
        raise PermissionError('Contest is not found!')
    else:
        # save_log(OAuthToken.json()['error_description'], 'while getting submission',
        # token, contest_id, submission_id)
        raise RuntimeError('Oops! Something went wrong. We are already working to fix it!')


def submissions_info(token: str, contest_id: str, from_pos: int = None, to_pos: int = None):
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

    result = requests.get(yandex_host + '/contests/' + contest_id + '/submissions', headers=headers, params=params)

    if result.status_code == 200:
        result = result.json()['submissions']

        if from_pos is not None:
            from_pos -= 1
            result = result[from_pos:to_pos]

        return result
    elif result.status_code == 403:
        raise PermissionError('You do not have permission to this contest!')
    elif result.status_code == 404:
        raise PermissionError('Contest is not found!')
    else:
        # save_log(OAuthToken.json()['error_description'], 'while getting submissions info',
        # token, contest_id, from_pos, to_pos)
        raise RuntimeError('Oops! Something went wrong. We are already working to fix it!')


# need async
def submissions(token: str, contest_id: str, from_pos: int = None, to_pos: int = None):
    try:
        submission_list = submissions_info(token, contest_id, from_pos, to_pos)

        submissions_result = list()
        for submission_info in submission_list:
            submission_source = submission(token, contest_id, str(submission_info['id']))
            submission_info['source'] = submission_source
            submissions_result.append(submission_info)

        return submissions_result
    except Exception as e:
        raise e
