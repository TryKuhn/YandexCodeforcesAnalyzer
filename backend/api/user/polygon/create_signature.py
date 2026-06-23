from hashlib import sha512
from random import randrange


def create_signature(method_name: str, params: dict[str, str], secret: str) -> str:
    """Build a Polygon API ``apiSig`` for the given method and params.

    Polygon requires the signature to be ``rand + sha512(rand/method?sorted_params#secret)``
    where ``rand`` is a fixed 6-digit random prefix and params are sorted by key.
    """
    sorted_params = sorted(params.items())
    random_string = f"{randrange(1000000):06d}"

    signature_string = f'{random_string}/{method_name}?{"&".join([f"{k}={v}" for k, v in sorted_params])}#{secret}'

    hash_signature = sha512(signature_string.encode()).hexdigest()

    return f"{random_string}{hash_signature}"
