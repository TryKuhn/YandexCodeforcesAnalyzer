from yandex_parser.api.login import link, token
from yandex_parser.api.standings import standings
from yandex_parser.api.submissions import submissions


class ApiYandex:

    get_link = link
    get_token = token

    get_standings = standings
    get_submissions = submissions
