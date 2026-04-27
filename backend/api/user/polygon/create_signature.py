from hashlib import sha512
from random import randrange


def create_signature(method_name: str, params: dict[str, str], secret: str) -> str:
    sorted_params = sorted(params.items())
    random_string = f"{randrange(1000000):06d}"

    signature_string = f'{random_string}/{method_name}?{"&".join([f"{k}={v}" for k, v in sorted_params])}#{secret}'

    hash_signature = sha512(signature_string.encode()).hexdigest()

    return f"{random_string}{hash_signature}"
