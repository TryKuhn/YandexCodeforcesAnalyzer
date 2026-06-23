"""Codeforces API request signing (``apiSig``)."""
from hashlib import sha512
from random import randrange


async def create_signature(
    method_name: str, params: dict[str, str], secret: str
) -> str:
    """Build the Codeforces API ``apiSig`` for a signed request.

    Prepends a random 6-digit nonce to the canonical
    ``rand/method?sorted_params#secret`` string, hashes it with SHA-512, and
    returns the nonce concatenated with the hex digest, as the API requires.
    """
    sorted_params = sorted(params.items())
    random_string = f"{randrange(1000000):06d}"

    signature_string = f'{random_string}/{method_name}?{"&".join([f"{k}={v}" for k, v in sorted_params])}#{secret}'

    hash_signature = sha512(signature_string.encode()).hexdigest()

    return f"{random_string}{hash_signature}"
