from hashlib import sha512
from random import randrange
from time import time

from settings import DEFAULT_PAGE_SIZE


def gen_borders(from_pos: str | None, to_pos: str | None):
    if from_pos is None:
        from_pos = 1
    if to_pos is None:
        to_pos = from_pos + DEFAULT_PAGE_SIZE - 1

    return from_pos, to_pos


def sign_request(method_name: str, api_secret: str, params: dict[str, str]) -> str:
    params = sorted(params.items(), key=lambda item: item[0:])
    rand = str(randrange(1000000)).zfill(6)

    s = f'{rand}/{method_name}?{"&".join([f"{x}={y}" for x, y in params])}#{api_secret}'

    hasher = sha512(s.encode()).hexdigest()
    return f'{rand}{hasher}'


def gen_params(oauth: tuple[str, str], method_name: str, **kwargs) -> list[tuple[str, str]]:
    millis = int(round(time()))

    params = {str(k): str(v) for k, v in kwargs.items() if v is not None}
    params['asManager'] = 'false'
    params['time'] = str(millis)
    params['apiKey'] = oauth[0]

    if 'From' in params:
        params['from'] = params['From']
        params.pop('From')

    params['apiSig'] = sign_request(method_name, oauth[1], params)

    params = [(k, v) for k, v in params.items()]

    return params
